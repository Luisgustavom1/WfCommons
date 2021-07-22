#!/usr/bin/python3

import pathlib
import argparse
import subprocess 


this_dir = pathlib.Path(__file__).resolve().parent

def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="Task Name")
    return parser 


def main():
    parser = get_parser()
    args, other = parser.parse_known_args()
    name = args.name

    save_dir = [item for item in other if "save" in item][0]
    save_dir = pathlib.Path(save_dir.split("=")[1]) 

    for path in save_dir.glob("*test_file*"):
        _, rest = path.name.split("test_file", 1)
        path.rename(path.parent.joinpath(f"test_file{rest}"))

    sysbench_file_input_args = [arg for arg in other if arg.startswith("--file")]   
    to_remove = [item for item in sysbench_file_input_args if "num" in item]
    sysbench_file_input_args.remove(to_remove[0])
 
    with save_dir.joinpath(f"{name}_fileio_run.txt").open("w+") as fp:
        proc = subprocess.Popen(["sysbench", "fileio", *sysbench_file_input_args, "run"], stdout=fp, stderr=fp)
        proc.wait()

    with save_dir.joinpath(f"{name}_fileio_cleanup.txt").open("w+") as fp:
        proc = subprocess.Popen(["sysbench", "fileio", *sysbench_file_input_args, "cleanup"], stdout=fp, stderr=fp)
        proc.wait()

    with save_dir.joinpath(f"{name}_cpu.txt").open("w+") as fp:
        sysbench_cpu_args = [arg for arg in other if arg.startswith("--cpu")]
        proc = subprocess.Popen(["sysbench", "cpu", "run", *sysbench_cpu_args], stdout=fp, stderr=fp)
        proc.wait()
    
    with save_dir.joinpath(f"{name}_memory.txt").open("w+") as fp:
        sysbench_mem_args = [arg for arg in other if arg.startswith("--memory")]
        proc = subprocess.Popen(["sysbench", "memory", "run", *sysbench_mem_args], stdout=fp, stderr=fp)
        proc.wait()

    with save_dir.joinpath(f"{name}_fileio_output.txt").open("w+") as fp:
        sysbench_file_output_args = [arg for arg in other if arg.startswith("--file")]
        proc = subprocess.Popen(["sysbench", "fileio", *sysbench_file_output_args, "prepare"], stdout=fp, stderr=fp)
        proc.wait()
    
    for path in this_dir.glob("*test_file*"):
        path.rename(path.parent.joinpath(f"{save_dir}/{args.name}_{path.name}"))

if __name__ == "__main__":
    main()