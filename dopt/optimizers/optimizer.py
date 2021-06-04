import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Union, Tuple, Optional
import json
import math
from os import path
import random

import torch
import numpy as np

from multiprocessing.connection import Connection

from dopt.utils import generate_seed

# TODO: Use logging instead of print
# Multiple objective functions?
# TODO: Deal with ordering problem
class Optimizer(ABC):
    r"""Abstract base class for hyperparameter optimizers.
    Optimizer distributes candidates (sets of hyperparameters)
    to Trainers, each of which is on a different machine to 
    compute the objective function in parallel.
    """
    MAX_OBSERVATIONS = 500
    HEADER_REMOVE_CANDIDATE = "Remove: "

    def __init__(self, 
                 filename: str,
                 bounds: Dict[str, Tuple[float, float]],
                 seed: Optional[int] = random.randint(1, 100000)) -> None:
        r""" Constructor for Optimizer base class.
        
        :param filename:   Name of the file
                            that stores observations
        :param bounds:      Boundaries to the search space
        :param seed:        To ensure reproducibility
        """
        self.filename = filename
        self.bounds = dict(sorted(bounds.items()))
        
        # Ensure reproducibility
        random.seed(seed)
        torch.manual_seed(generate_seed())
        np.random.seed(generate_seed())
        
        # List of observed points:
        # [{"candidate":..., "result":...}, ...}]
        self.observations: List[Dict[str, Dict]] = []
        self._load_observations()
        
        # List of pending hyperparameters, length = number of Trainers
        # [{"num_batch":..., "num_iter":...}, ...]
        self.pending_candidates: List[Dict[str, Dict]] = []
            
        # Connection with server
        self.server_conn = None
        
    def _set_server_connection(self, conn):
        if self.server_conn == None:
            self.server_conn = conn
        else:
            raise Exception("Connection with server already established")
            
    def is_running(self) -> bool:
        r"""Determine where the optimizer will stop. Override the
        function to add stopping condition."""
        if len(self.observations) > Optimizer.MAX_OBSERVATIONS:
            return False
        return True
    
    def get_labels(self):
        return self.bounds.keys()
    
    def _load_observations(self):
        r"""Load observations from existing file. If file doesn't
        exist, create a new file"""
        if path.exists(self.filename):
            # Load observations
            with open(self.filename, "r") as f:
                for line in f.readlines():
                    self.observations.append(json.loads(line))
        else:
            # Create a new file
            with open(self.filename, "w") as f:
                pass
    
    def _save_observation(self, observation):
        r"""Save ONE acquired observation into a storing file"""
        with open(self.filename, "a") as f:
            f.write(json.dumps(observation, indent=None) + "\n")
            
    def remove_pending_candidate(self, observation):
        """Candidates from returning observations, successful or failed,
        are to be removed from the pending_candidates list
        
        :param observation: A single observation
        """
        candidate_to_remove = observation["candidate"]
        if candidate_to_remove not in self.pending_candidates:
            raise Exception("Candidate not found in pending candidates!")
        self.pending_candidates = [candidate 
                                   for candidate in self.pending_candidates
                                   if candidate != candidate_to_remove]

    def run(self, conn, logger, lock) -> None:
        """Optimization loop. 
        Generate candidate to send to Server, then receive further
        candidate(s) from Server, and then generate, and so
        on."""
        self._set_server_connection(conn)
        while self.is_running():
            try:
                responses = self.server_conn.recv()
                with lock:
                    logger.debug(f"Optimizer received: {responses}")
            except EOFError:
                # When the other end is closed
                with lock:
                    logger.debug("Exitting Optimizer")
                return
            
            # Handle the server's response(s)
            for response in responses.split("\n")[:-1]:    
                response = response.strip()
                if response == "{}":
                    pass
                elif Optimizer.HEADER_REMOVE_CANDIDATE in response:
                    # Remove pending candidate
                    candidate = json.loads(response[len(Optimizer.HEADER_REMOVE_CANDIDATE):].strip())
                    self.remove_pending_candidate({"candidate": candidate})
                    with lock:
                        logger.debug(f"Removed candidate: {candidate}")
                    continue
                else:
                    observation = json.loads(response)
                    if observation["contention_failure"] == False:
                        self.observations.append(observation)
                        self._save_observation(observation) 
                    self.remove_pending_candidate(observation) 
                
                 # Find one potential candidate to try next based on the info
                candidate: Dict[str, Any] = self.generate_candidate()
                candidate["id"] = self.generate_id()
                self.pending_candidates.append(candidate)

                reply = json.dumps({"candidate": candidate})
                self.server_conn.send(reply)                # <---- This
                with lock:
                    logger.debug(f"Optimizer sent: {reply}")
                
            with lock:
                logger.debug(f"Number of observations: {len(self.observations)}")
                logger.debug(f"Number of pending candidates: {len(self.pending_candidates)}")
                logger.debug(f"Pending candidates: {json.dumps(self.pending_candidates)}")
                logger.warning(f"Pending candidates: {json.dumps(self.pending_candidates)}")
          
            
    def generate_id(self):
        current_ids = [o["candidate"]["id"] for o in self.observations]
        current_ids += [candidate["id"] for candidate in self.pending_candidates]
        i = 1
        while i <= len(current_ids) + 1:
            if i not in current_ids:
                break
            i += 1    
        return i
        
    @abstractmethod
    def generate_candidate(self) \
            -> Dict[str, Any]:
        r"""Draw the best candidate to evaluate based on known observations."""
        raise NotImplementedError
            
