
### How to use
We'll be running `distributed_optimizer.py` to start the optimization.
  
`distributed_optimizer.py`  can be run in 2 modes: host mode and client mode. 
The host mode will call 2 processes: One that
 starts the  `Optimizer` of choice and One that connect with other machines (the clients) to run `distributed_optimizer.py` on client mode. 
 The client mode will run the user-specified MyWhateverTrainer.
 Host mode: `python3 distributed_optimizer.py` as host mode is the default.
 Client mode: `python3 distributed_optimizer.py --run_as=client` as client mode. You do *not* need to manually run client mode on each client machine as the host mode will do this. However, you can use it if you want to add client machines during optimization.

Essential parts of the script:
- The COMMANDS: A constant dictionary. The keys are machine categories, and values are the necessary commands to run `distributed_optimizer.py` on client mode on those different categories.

 - A MyWhateverTrainer that inherits the `Trainer` abstract class from 
 `src.trainer`, and implement the abstract method `get_observation`, in which the set of hyperparameters (candidate) given will be plugged into the objective function.
  
 - A `start_host()` function that will be used to call 2 processes: one that
 start the `Optimizer` and one that runs appropriate sequence of commands to run `distributed_optimizer.py` on client mode, i.e. start`Trainers` on respective machines using the following:
 `python3 distributed_optimizer.py --run_as=client`

- A `start_client()` function that will run MyWhateverTrainer, i.e. run objective function.

- A `main()` that parse command line input and switch between host and client mode, and specify further information needed to run objective function on target machines.
  
Check list:
 - Step 1: Create your specified `MyWhatever Trainer` that implements the `get_observation` method.
 - Step 2: Make sure the appropriate environment can be chosen through ssh tunneling. Try: `ssh [name]@[hostmachine] [YOUR COMMANDS]`
 - Step 3: Add the commands to the `COMMANDS` dictionary.
 - Step 4: Make sure you have a copy of the `distributed_optimizer.py` and related files on all of the machines you intend to use