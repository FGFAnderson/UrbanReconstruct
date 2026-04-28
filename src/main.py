import argparse

from .pipeline import Pipeline, PipelineContext
from .stages.colmap_reconstruction import ColmapMvsStage, ColmapStage
from .stages.image_preprocessing import ImagePreprocessingStage
from .stages.mpsfm_reconstruction import MpSfmStage


def main():
    parser = argparse.ArgumentParser(description="Urban 3D reconstruction pipeline")
    parser.add_argument(
        "--input_dir",
        type=str,
        default="/home/fin/doccuments/work/UrbanReconstruct/src/data_acquisition/geo_data/51.8894_0.9083_51.8903_0.9100_360_small/images",
        help="Input directory containing images",
    )
    parser.add_argument(
        "--stage",
        choices=["colmap", "mpsfm", "mpsfm-dense"],
        default="colmap",
        help="Reconstruction backend to use (default: colmap)",
    )
    parser.add_argument(
        "--dense",
        action="store_true",
        help="Run COLMAP patch-match MVS after SfM (all stages), or COLMAP dense for --stage colmap",
    )
    args = parser.parse_args()

    # 360° images converted to PINHOLE rectilinear: fx=fy=cx=cy=512 for 1024×1024 at 90° FOV
    PINHOLE_PARAMS = [512.0, 512.0, 512.0, 512.0]

    if args.stage == "colmap":
        reconstruction_stages = [
            ColmapStage(
                output_dir="colmap_output",
                matcher="exhaustive",
                dense=args.dense,
            )
        ]
    else:
        conf = "sp-mast3r-dense" if args.stage == "mpsfm-dense" else "sp-lg_m3dv2"
        reconstruction_stages = [
            MpSfmStage(
                output_dir="mpsfm_output",
                conf=conf,
                camera_params=PINHOLE_PARAMS,
            ),
            ColmapMvsStage(output_dir="mvs_output"),
        ]

    pipeline = Pipeline(
        stages=[
            ImagePreprocessingStage(output_dir="preprocessed_images"),
            *reconstruction_stages,
        ]
    )

    ctx = PipelineContext(input_dir=args.input_dir)

    print(f"Running {args.stage.upper()} pipeline on: {args.input_dir}")
    result = pipeline.run(ctx)

    if result.errors:
        print("\nPipeline failed with errors:")
        for error in result.errors:
            print(f"  - {error}")
    else:
        print("\nPipeline completed successfully!")
        print(f"  Point cloud: {result.data['point_cloud_path']}")


if __name__ == "__main__":
    main()
