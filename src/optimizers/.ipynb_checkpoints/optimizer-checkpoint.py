import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Union, Tuple
import json

import torch

# TODO: Use logging instead of print
# TODO: Save observations into a log file
# TODO: Add checkpoint functionality
class Optimizer(ABC):
    r"""Abstract base class for hyperparameter optimizers.
    Optimizer distributes candidates (sets of hyperparameters)
    to Trainers, each of which is on a different machine to 
    compute the objective function in parallel.
    """
    MAX_OBSERVATIONS = 500

    def __init__(self, 
                 bounds: Dict[str, Tuple[float, float]]) -> None:
        r""" Constructor for Optimizer base class.
        
        :param bounds: Boundaries to the search space
        """
        self.loop = asyncio.get_event_loop()
        self.num_trainers = 0
        self.bounds = bounds
        # List of observed points:
        # [{"candidate":..., "result":...}, ...}]
        self.observations: List[Dict[str, Dict]] = []
        # List of pending hyperparameters, length = number of Trainers
        # [{"num_batch":..., "num_iter":...}, ...]
        self.pending_candidates: List[Dict[str, Dict]] = []
            
    @property
    def is_running(self) -> bool:
        if len(self.observations) > MAX_OBSERVATIONS:
            return False
        return True
    
    def get_labels(self):
        return self.bounds.keys()

    def run(self, host="127.0.0.1", port="15555") -> None:
        """ Runs server at specified host and port.

        :param host: TODO
        :param port:
        """
        asyncio.run(self._start_server(host, port))

    async def _start_server(self, host, port) -> None:
        server = await asyncio.start_server(self._handle_trainer,
                                            host, port)
        address = server.sockets[0].getsockname()
        print(f'Serving on {address}')
        async with server:
            await server.serve_forever()

    async def _handle_trainer(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter) -> None:
        r"""Handle a single Trainer. Receive incoming candidate request
        and send one potential candidate to the Trainer

        :param reader: TODO
        :param writer:
        """
        print(f"Connected with Trainer at "
              f"{writer.get_extra_info('peername')}")
        self.num_trainers += 1
        
        # Add an empty slot to accomodate the pending candidate from the Trainer
        trainer_index = self.num_trainers - 1
        self.pending_candidates.append(None) 
        
        trainer_info = None
        while self.is_running():
            
            # Find one potential candidate to try next based on the info
            candidate: Dict[srt, Any] = self.generate_candidate(candidate, trainer_info)
            
            # Send candidate to Trainer
            out_message = json.dumps(candidate)
            writer.write(out_message.encode("utf8"))
            await writer.drain()
            self.pending_candidates[trainer_index] = candidate
            
            # Receive info of the Trainer including training result(s)
            in_message: str = (await reader.read(255)).decode("utf8")
            trainer_info: Dict = json.loads(in_message)
                
            self.observations.append({"candidate": candidate, "result": trainer_info["result"]})
            self.pending_candidates[trainer_index] = None
            
        writer.close()
        self.num_trainers -= 1
        print(f"Closing Trainer at {writer.get_extra_info('peername')}")

    @abstractmethod
    def generate_candidate(self, candidate: Dict[str, Any], trainer_info: Dict) -> Dict[str, Any]:
        r"""Draw the best candidate to evaluate.

        :param candidate: 
        :param trainer_info: Dictionary containing TODO
        """
        raise NotImplementedError
            