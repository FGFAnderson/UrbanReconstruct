"""
MapAnything Inference

Library for running MapAnything inference to generate 3D reconstructions.
"""

import os

import numpy as np
import torch

from mapanything.models import MapAnything
from mapanything.utils.geometry import depthmap_to_world_frame
from mapanything.utils.image import load_images
from mapanything.utils.viz import predictions_to_glb

from ..pipeline import PipelineContext, Stage


def run_inference(
    image_folder: str,
    glb_path: str = "output.glb",
    resolution: int = 518,
):
    """Run MapAnything inference and generate GLB output.

    Args:
        image_folder: Path to folder containing images
        glb_path: Path to save GLB file (default: output.glb)
        resolution: Image resolution for inference (default: 518)
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = MapAnything.from_pretrained("facebook/map-anything").to(device)

    # Load images
    views = load_images(image_folder, resolution_set=resolution)
    views = views[: len(views) // 4]

    # Run inference
    outputs = model.infer(
        views,
        memory_efficient_inference=True,
        minibatch_size=1,
        use_amp=True,
        amp_dtype="fp16",
        apply_mask=True,
        mask_edges=True,
    )

    # Prepare and save GLB
    world_points_list = []
    images_list = []
    masks_list = []

    for pred in outputs:
        depthmap_torch = pred["depth_z"][0].squeeze(-1)
        intrinsics_torch = pred["intrinsics"][0]
        camera_pose_torch = pred["camera_poses"][0]

        pts3d_computed, valid_mask = depthmap_to_world_frame(
            depthmap_torch, intrinsics_torch, camera_pose_torch
        )

        mask = pred["mask"][0].squeeze(-1).cpu().numpy().astype(bool)
        mask = mask & valid_mask.cpu().numpy()

        pts3d_np = pts3d_computed.cpu().numpy()
        image_np = pred["img_no_norm"][0].cpu().numpy()

        world_points_list.append(pts3d_np)
        images_list.append(image_np)
        masks_list.append(mask)

    # Stack all views
    world_points = np.stack(world_points_list, axis=0)
    images = np.stack(images_list, axis=0)
    final_masks = np.stack(masks_list, axis=0)

    # Create predictions dict for GLB export
    predictions = {
        "world_points": world_points,
        "images": images,
        "final_masks": final_masks,
    }

    # Convert to GLB scene
    scene_3d = predictions_to_glb(predictions, as_mesh=True)

    # Save GLB file
    os.makedirs(os.path.dirname(glb_path) or ".", exist_ok=True)
    scene_3d.export(glb_path)


class MapAnythingStage(Stage):
    """Pipeline stage for MapAnything inference."""

    def __init__(
        self,
        glb_path: str = "output.glb",
        resolution: int = 518,
    ):
        """Initialise MapAnything stage.

        Args:
            glb_path: Path to save GLB file
            resolution: Image resolution for inference
        """
        self.glb_path = glb_path
        self.resolution = resolution

    def run(self, ctx: PipelineContext) -> PipelineContext:
        """Run MapAnything inference on images in context.

        Args:
            ctx: Pipeline context with input_dir

        Returns:
            Updated context with inference outputs and any errors
        """
        try:
            if not ctx.input_dir:
                ctx.errors.append("No input directory provided")
                return ctx

            # Run inference
            run_inference(
                image_folder=ctx.input_dir,
                glb_path=self.glb_path,
                resolution=self.resolution,
            )

            # Store output path in context
            ctx.glb_path = self.glb_path

        except Exception as e:
            ctx.errors.append(f"MapAnything inference failed: {str(e)}")

        return ctx
