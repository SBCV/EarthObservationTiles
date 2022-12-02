import toml
from pydantic import BaseModel
from typing import List, Tuple, Dict, Union
from eot.config.ai_config import AIConfig


class ProxyConfig(BaseModel):
    ip_str: str = None
    port_str: str = None


class RetrieveConfig(BaseModel):
    retrieve_dataset_from_folder: bool = False
    downloaded_dataset_dp: str = None
    retrieve_dataset_from_archive: bool = False
    retrieve_dataset_from_web: bool = False
    tar_fp: str = None


class DatasetEntry(BaseModel):
    # dn = directory name
    dn: str
    dataset_type: str


class RegexEntry(BaseModel):
    # dn = directory name
    dn: str
    regex: str


class BandEntry(BaseModel):
    # dn = directory name
    dn: str
    bands: List[int]


class DataConfig(BaseModel):
    train_datasets: List[DatasetEntry]
    test_datasets: List[DatasetEntry]
    image_search_regex: List[RegexEntry]
    image_ignore_regex: List[RegexEntry]
    label_search_regex: List[RegexEntry]
    label_ignore_regex: List[RegexEntry]
    image_bands: List[BandEntry]
    label_bands: List[BandEntry]
    workspace_dp: str
    data_category_titles: List[str] = None
    training_category_titles: List[str] = None
    invalid_category_target_index: int = 0


class TileConfig(BaseModel):
    # NB: tile_size = (tile_width, tile_height)
    tiling_scheme: str
    input_tile_zoom_level: int = None
    input_tile_size_in_pixel: Tuple[int, int] = None
    input_tile_size_in_meter: Tuple[float, float] = None
    # Stride values used for training
    input_train_tile_stride_in_pixel: Tuple[
        int, int
    ] = input_tile_size_in_pixel
    input_train_tile_stride_in_meter: Tuple[
        float, float
    ] = input_tile_size_in_meter
    input_train_tile_overhang: Union[bool, int] = False
    input_train_tile_keep_border_tiles: Union[bool, int] = False

    input_test_tile_stride_in_pixel: Tuple[int, int] = input_tile_size_in_pixel
    input_test_tile_stride_in_meter: Tuple[
        float, float
    ] = input_tile_size_in_meter
    input_test_tile_overhang: Union[bool, int] = False
    input_test_tile_keep_border_tiles: Union[bool, int] = False

    # Skip tile if nodata pixel ratio > threshold (i.e. 100 == "keep all")
    no_data_threshold: int = 100


class PipelineStepConfig(BaseModel):
    prepare_training_data: Union[bool, int]
    run_training: Union[bool, int]
    export_model_complexity: Union[bool, int]
    prepare_test_data: Union[bool, int]
    compute_test_predictions: Union[bool, int]
    evaluate_test_predictions: Union[bool, int]
    aggregate_test_predictions: Union[bool, int]
    compare_test_predictions_with_labels: Union[bool, int]

    lazy: Union[bool, int]

    resume_training: Union[bool, int] = False
    deterministic_training: Union[bool, int] = False

    disable_train_pipeline_vertical_flip: Union[bool, int] = False
    disable_train_pipeline_rotation: Union[bool, int] = False
    disable_train_pipeline_resizing: Union[bool, int] = False
    disable_test_pipeline_resizing: Union[bool, int] = False

    prediction_train_model_checkpoint_fn: str = "latest.pth"

    perform_prediction_base_tile_evaluation: Union[bool, int] = False
    perform_prediction_base_tile_merging: Union[bool, int] = False
    ignore_background_category_in_evaluation: Union[bool, int] = False

    eval_metrics: list

    aggregate_as_images: Union[bool, int] = True
    aggregate_as_json: Union[bool, int] = True
    aggregate_as_global_json: Union[bool, int] = True
    aggregate_save_normalized_raster: Union[bool, int] = True

    create_image_json_vis: Union[bool, int] = False
    create_label_json_vis: Union[bool, int] = False
    create_tile_aux_files: Union[bool, int] = False
    debug_prediction_merging: Union[bool, int] = False
    debug_prediction_create_mmseg_pkl_file: Union[bool, int] = False
    debug_prediction_load_mmseg_pkl_file: Union[bool, int] = False
    debug_prediction_max_number_tiles_per_image: int = None
    clear_split_data: Union[bool, int] = True


class ParsedBaseModel(BaseModel):
    @classmethod
    def get_from_file(cls, toml_ifp):
        config_dict = toml.load(toml_ifp)
        return cls(**config_dict)


class WrappedAIConfig(ParsedBaseModel):
    ai_config: AIConfig


class PipelineConfig(ParsedBaseModel):
    data_config: DataConfig
    tile_config: TileConfig
    pipeline_step_config: PipelineStepConfig
    ai_config: AIConfig
    proxy_config: ProxyConfig = ProxyConfig()

    retrieve_config: RetrieveConfig = RetrieveConfig()
