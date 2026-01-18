import argparse
import os
from poisson_reconstruction import poisson_reconstruction

def main():
    parser = argparse.ArgumentParser(
        description="Create 3d meshes from supported data formats"
    )
    parser.add_argument(
        "input_path",
        type=str,
        help="Input point cloud file (.ply)"
    )
    parser.add_argument(
        "output_dir",
        type=str,
        help="Output directory for mesh file",
        nargs="?",
        default="."
    )
    
    args = parser.parse_args()
    
    if not os.path.isfile(args.input_path):
        print(f"Error: Input file '{args.input_path}' does not exist")
        return
    
    poisson_reconstruction(args.input_path, args.output_dir)
    print(f"Done! Processed mesh saved to '{args.output_dir}'")


if __name__ == "__main__":
    main()
