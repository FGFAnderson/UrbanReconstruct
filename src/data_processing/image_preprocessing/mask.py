import argparse
import os

import cv2
import numpy as np
from ultralytics import YOLO

model = YOLO("yolo11x-seg.pt")

dynamic_classes = ["car", "person", "bicycle", "motorcycle", "bus", "truck"]


def remove_dynamic_objects(image):
    """Remove dynamic objects from image using YOLO segmentation and inpainting

    Args:
        image: Input image array

    Returns:
        Image with dynamic objects inpainted
    """
    results = model(image)
    mask = np.zeros(image.shape[:2], dtype=np.uint8)

    for result in results:
        if result.masks is None:
            continue
        for seg, cls in zip(result.masks.xy, result.boxes.cls):
            if model.names[int(cls)] in dynamic_classes:
                # Fill masked region with 1
                cv2.drawContours(mask, [seg.astype(np.int32)], 0, 1, thickness=-1)

    # Inpaint masked regions
    if np.any(mask):
        inpainted = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)
        return inpainted

    return image


def process_images(
    input_dir: str, output_dir: str, save_masks_only: bool = False
) -> None:
    """Process all images in input directory and remove dynamic objects

    Args:
        input_dir (str): directory of images
        output_dir (str): directory to output processed images or masks
        save_masks_only (bool): If True, save only binary masks; if False, save inpainted images
    """
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        input_path = os.path.join(input_dir, filename)

        print(f"Processing: {filename}")
        image = cv2.imread(input_path)

        if image is None:
            print(f"  Error: Could not read {filename}")
            continue

        # Generate mask
        results = model(image)
        mask = np.zeros(image.shape[:2], dtype=np.uint8)

        for result in results:
            if result.masks is None:
                continue
            for seg, cls in zip(result.masks.xy, result.boxes.cls):
                if model.names[int(cls)] in dynamic_classes:
                    cv2.drawContours(mask, [seg.astype(np.int32)], 0, 1, thickness=-1)

        if save_masks_only:
            # Save binary mask only
            output_path = os.path.join(output_dir, filename)
            cv2.imwrite(output_path, mask * 255)  # Save as 0-255 for clarity
            print(f"  Saved mask to: {output_path}")
        else:
            # Save inpainted image
            if np.any(mask):
                processed = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)
            else:
                processed = image
            output_path = os.path.join(output_dir, filename)
            cv2.imwrite(output_path, processed)
            print(f"  Saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Remove dynamic objects from images using YOLO segmentation"
    )
    parser.add_argument("input_dir", type=str, help="Input directory containing images")
    parser.add_argument(
        "output_dir", type=str, help="Output directory for processed images or masks"
    )
    parser.add_argument(
        "--save_masks_only",
        action="store_true",
        default=False,
        help="Save only binary masks (for point cloud filtering) instead of inpainted images",
    )

    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        print(f"Error: Input directory '{args.input_dir}' does not exist")
        return

    process_images(
        args.input_dir, args.output_dir, save_masks_only=args.save_masks_only
    )
    if args.save_masks_only:
        print(f"Done! Masks saved to '{args.output_dir}'")
    else:
        print(f"Done! Processed images saved to '{args.output_dir}'")


if __name__ == "__main__":
    main()
