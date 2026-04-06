import argparse
import os
import pickle
from pathlib import Path

import cv2
import numpy as np


def load_mapanything_outputs(outputs_dir: str):
    """Load MapAnything inference outputs

    Args:
        outputs_dir: Directory containing MapAnything pickle outputs

    Returns:
        List of dicts with keys: pts3d, intrinsics, camera_poses, mask, img_no_norm
    """
    outputs = []
    output_files = sorted(Path(outputs_dir).glob("*.pkl"))

    for pkl_file in output_files:
        with open(pkl_file, "rb") as f:
            data = pickle.load(f)
            outputs.append(data)

    return outputs


def write_ply(points, colors, output_path: str):
    """Write point cloud to PLY file

    Args:
        points: Nx3 array of 3D points
        colors: Nx3 array of RGB colors (0-255)
        output_path: Path to save PLY file
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    # Convert colors to uint8 if needed
    if colors.dtype != np.uint8:
        colors = (
            (colors * 255).astype(np.uint8)
            if colors.max() <= 1.0
            else colors.astype(np.uint8)
        )

    # Create structured array for PLY format
    vertex_data = np.zeros(
        len(points),
        dtype=[
            ("x", "f4"),
            ("y", "f4"),
            ("z", "f4"),
            ("red", "u1"),
            ("green", "u1"),
            ("blue", "u1"),
        ],
    )

    vertex_data["x"] = points[:, 0]
    vertex_data["y"] = points[:, 1]
    vertex_data["z"] = points[:, 2]
    vertex_data["red"] = colors[:, 0]
    vertex_data["green"] = colors[:, 1]
    vertex_data["blue"] = colors[:, 2]

    # Write PLY file
    with open(output_path, "wb") as f:
        # Write header
        f.write(b"ply\n")
        f.write(b"format binary_little_endian 1.0\n")
        f.write(f"element vertex {len(points)}\n".encode())
        f.write(b"property float x\n")
        f.write(b"property float y\n")
        f.write(b"property float z\n")
        f.write(b"property uchar red\n")
        f.write(b"property uchar green\n")
        f.write(b"property uchar blue\n")
        f.write(b"end_header\n")

        # Write binary data
        f.write(vertex_data.tobytes())


def filter_pointcloud_by_masks(
    mapanything_outputs: list,
    masks_dir: str,
    output_path: str = "filtered_pointcloud.ply",
):
    """Filter MapAnything point cloud by removing points in dynamic regions

    Args:
        mapanything_outputs: List of MapAnything output dicts
        masks_dir: Directory containing mask images from mask.py
        output_path: Path to save filtered point cloud
    """
    all_points = []
    all_colors = []

    masks_path = Path(masks_dir)
    mask_files = sorted(masks_path.glob("*.png"))

    if len(mask_files) != len(mapanything_outputs):
        print(
            f"Warning: Found {len(mask_files)} masks but {len(mapanything_outputs)} MapAnything outputs"
        )

    # Process each view
    for view_idx, (pred, mask_file) in enumerate(zip(mapanything_outputs, mask_files)):
        print(f"Processing view {view_idx}: {mask_file.name}")

        # Extract MapAnything data
        pts3d = pred["pts3d"]  # (H, W, 3)
        valid_mask = pred["mask"]  # (H, W) - points valid in reconstruction
        image = pred["img_no_norm"]  # (H, W, 3)

        # Load dynamic object mask
        dynamic_mask = cv2.imread(str(mask_file), cv2.IMREAD_GRAYSCALE)

        if dynamic_mask is None:
            print(f"  Error: Could not read mask {mask_file.name}")
            continue

        # Ensure masks are same size as image
        h, w = image.shape[:2]
        if dynamic_mask.shape != (h, w):
            dynamic_mask = cv2.resize(
                dynamic_mask, (w, h), interpolation=cv2.INTER_NEAREST
            )

        # Create filter: keep points that are:
        # 1. Valid in reconstruction
        # 2. NOT in dynamic regions (dynamic_mask == 0)
        keep_mask = valid_mask & (dynamic_mask == 0)

        # Extract filtered points and colors
        valid_points = pts3d[keep_mask]  # (N, 3)
        valid_colors = image[keep_mask]  # (N, 3)

        all_points.append(valid_points)
        all_colors.append(valid_colors)

        print(
            f"  Kept {len(valid_points)} / {np.sum(valid_mask)} points (removed {np.sum(dynamic_mask & valid_mask)})"
        )

    # Combine all points
    if not all_points:
        print("Error: No valid points to save")
        return

    combined_points = np.vstack(all_points)
    combined_colors = np.vstack(all_colors)

    # Normalize colors to [0, 255] if needed
    if combined_colors.max() <= 1.0:
        combined_colors = combined_colors * 255.0

    # Write PLY file
    write_ply(combined_points, combined_colors, output_path)
    print(f"\nSaved filtered point cloud: {output_path}")
    print(f"Total points: {len(combined_points)}")


def main():
    parser = argparse.ArgumentParser(
        description="Filter MapAnything point cloud by removing dynamic object regions"
    )
    parser.add_argument(
        "--mapanything_outputs",
        type=str,
        required=True,
        help="Directory containing MapAnything pickle outputs",
    )
    parser.add_argument(
        "--masks_dir",
        type=str,
        required=True,
        help="Directory containing mask images from mask.py",
    )
    parser.add_argument(
        "--output_path",
        type=str,
        default="filtered_pointcloud.ply",
        help="Output path for filtered point cloud (default: filtered_pointcloud.ply)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.isdir(args.mapanything_outputs):
        print(
            f"Error: MapAnything outputs directory '{args.mapanything_outputs}' does not exist"
        )
        return

    if not os.path.isdir(args.masks_dir):
        print(f"Error: Masks directory '{args.masks_dir}' does not exist")
        return

    # Load MapAnything outputs
    print(f"Loading MapAnything outputs from: {args.mapanything_outputs}")
    outputs = load_mapanything_outputs(args.mapanything_outputs)
    print(f"Loaded {len(outputs)} MapAnything outputs")

    # Filter point cloud
    filter_pointcloud_by_masks(outputs, args.masks_dir, args.output_path)


if __name__ == "__main__":
    main()
