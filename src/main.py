"""
Example script to run MapAnything inference through the pipeline.
"""

from .stages.mapanything_inference import MapAnythingStage
from .pipeline import Pipeline, PipelineContext


def main():
    """Run MapAnything inference pipeline."""
    # Configuration
    INPUT_DIR = "/home/fin/doccuments/work/UrbanReconstruct/src/data_acquisition/carla_sim/out/20260407_035018"
    GLB_PATH = "output.glb"
    RESOLUTION = 518

    # Create pipeline with MapAnything stage
    pipeline = Pipeline(
        stages=[
            MapAnythingStage(
                glb_path=GLB_PATH,
                resolution=RESOLUTION,
            )
        ]
    )

    # Create context with input directory
    ctx = PipelineContext(input_dir=INPUT_DIR)

    # Run pipeline
    print(f"Running MapAnything pipeline on: {INPUT_DIR}")
    result = pipeline.run(ctx)

    # Handle results
    if result.errors:
        print("\n❌ Pipeline failed with errors:")
        for error in result.errors:
            print(f"  - {error}")
    else:
        print("\n✅ Pipeline completed successfully!")
        print(f"  GLB file: {result.glb_path}")


if __name__ == "__main__":
    main()
