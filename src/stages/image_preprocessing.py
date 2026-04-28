from pathlib import Path

from ..data_processing.image_preprocessing.main import prepare_images_for_colmap
from ..pipeline import PipelineContext, Stage


class ImagePreprocessingStage(Stage):
    """Convert 360 images to rectilinear perspective before reconstruction."""

    def __init__(self, output_dir: str = "preprocessed_images"):
        self.output_dir = output_dir

    def run(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.input_dir:
            ctx.errors.append("No input directory provided")
            return ctx

        output_path = Path(self.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        prepare_images_for_colmap(ctx.input_dir, str(output_path))

        ctx.input_dir = str(output_path)
        return ctx
