import os
import math
from fractions import Fraction
from functools import reduce
from eot.utility.os_ext import get_subdirs
from eot.utility.os_ext import get_file_paths_in_dir
from eot.rasters.raster import Raster
from eot.utility.np_ext import get_unique_color_list


class Dataset:
    def __init__(self):
        self._entries = []

    def __iter__(self):
        return iter(self._entries)

    @classmethod
    def retrieve_from_dp(
        cls,
        idp,
        image_ext_list=None,
        label_ext_list=None,
        label_dp_suffix="-labels",
    ):

        if image_ext_list is None:
            image_ext_list = [".tif"]

        if label_ext_list is None:
            label_ext_list = [".tif", ".geojson"]

        dp_list = get_subdirs(idp, base_name_only=False, recursive=False)
        assert len(dp_list) >= 2

        # Make sure that corresponding image_dp and label_dp folders are subsequent
        # items in the list
        dp_list = sorted(dp_list)

        dataset = cls()
        for idx, _ in enumerate(dp_list):
            if idx % 2 == 1:
                continue
            image_dp = dp_list[idx]
            label_dp = dp_list[idx + 1]

            if not image_dp + label_dp_suffix == label_dp:
                print("image_dp", image_dp)
                print("label_dp", label_dp)
                assert False

            image_fp_list = get_file_paths_in_dir(image_dp, ext=image_ext_list)
            label_fp_list = get_file_paths_in_dir(label_dp, ext=label_ext_list)
            label_raster_fp = label_geojson_fp = None
            assert len(image_fp_list) == 1
            image_fp = image_fp_list[0]

            assert len(label_fp_list) == 1 or len(label_fp_list) == 2
            for label_fp in label_fp_list:
                ext = os.path.splitext(label_fp)[1]
                if ext == ".tif":
                    label_raster_fp = label_fp
                if ext == ".geojson":
                    label_geojson_fp = label_fp

            entry = DatasetEntry(
                image_dp, label_dp, image_fp, label_raster_fp, label_geojson_fp
            )
            dataset.add_entry(entry)
        return dataset

    def get_entries(self, use_masks=False):
        if use_masks:
            result = [entry for entry in self._entries if not entry.masked]
        else:
            result = self._entries
        return result

    def add_entry(self, entry):
        self._entries.append(entry)

    def mask_entries(self, mask_func):
        # Do not use "map", because of its lazy behavior
        for entry in self._entries:
            mask_func(entry)

    def split_data_by_id(self, train_id_list, test_id_list):
        # TODO
        assert False

    @staticmethod
    def lcm(a, b):
        res = a * b // math.gcd(a, b)
        return res

    @classmethod
    def lcm_integer(cls, *numbers):
        # https://stackoverflow.com/questions/36551393/how-to-get-the-gratest-common-divisor-as-integer-in-python-from-a-list-of-floats
        fractions = [Fraction(n).limit_denominator() for n in numbers]
        multiple_factor = reduce(cls.lcm, [f.denominator for f in fractions])
        integers = [int(frac * multiple_factor) for frac in fractions]
        division_factor = reduce(math.gcd, integers)
        return [int(n / division_factor) for n in integers]

    def split_data_by_ratio(
        self,
        train_test_ratio=0.8,
        max_num_elements=None,
        use_masks=False,
    ):
        """A ratio of 0.8 means that 80% of the data is used for training."""

        entries = self.get_entries(use_masks=use_masks)
        if max_num_elements is not None:
            entries = entries[:max_num_elements]

        train_slice_length, test_slice_length = self.lcm_integer(
            train_test_ratio, (1 - train_test_ratio)
        )
        sequence_slice_length = train_slice_length + test_slice_length

        entry_indices = list(range(len(entries)))
        slice_start_indices = entry_indices[0::sequence_slice_length]
        slices = [
            entries[idx : idx + sequence_slice_length]
            for idx in slice_start_indices
        ]

        train_entries = []
        test_entries = []
        for slice in slices:
            current_train_slices = slice[0:train_slice_length]
            current_test_slices = slice[
                train_slice_length : train_slice_length + test_slice_length
            ]

            # The test slice must not be empty! Move the last training image to
            # the set of test images (if necessary).
            if len(current_test_slices) == 0:
                assert len(current_train_slices) >= 2
                current_test_slices.append(current_train_slices.pop())

            train_entries.extend(current_train_slices)
            test_entries.extend(current_test_slices)
        assert len(train_entries) + len(test_entries) == len(entries)
        return train_entries, test_entries


class DatasetEntry:
    def __init__(
        self,
        image_dp=None,
        label_dp=None,
        image_fp=None,
        label_raster_fp=None,
        label_geojson_fp=None,
        masked=False,
    ):
        self.image_dp = image_dp
        self.label_dp = label_dp
        self.image_fp = image_fp
        self.label_raster_fp = label_raster_fp
        self.label_geojson_fp = label_geojson_fp
        self.masked = masked
        self._label_values = None

    def get_id_str(self):
        return os.path.basename(self.image_dp)

    def __repr__(self):
        return self.get_id_str()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.get_id_str() == other.get_id_str()
        else:
            return False

    def __lt__(self, other):
        # Required for sorting
        assert isinstance(other, self.__class__)
        return self.get_id_str() < other.get_id_str()

    def __hash__(self):
        # A hash is required to use Tile within sets
        return hash(self.get_id_str())

    def compute_label_values(self):
        assert os.path.isfile(self.label_raster_fp)
        bands = [1, 2, 3]
        raster = Raster.get_from_file(self.label_raster_fp)
        raster_data_arr = raster.get_raster_data_as_numpy(indexes=bands)
        self._label_values = get_unique_color_list(raster_data_arr)

    def get_label_values(self):
        return self._label_values

    def contains_label_values(
        self, target_label_value_list, aggregator_func=all
    ):
        if self.get_label_values() is None:
            self.compute_label_values()

        present_label_value_list = self.get_label_values()
        present_label_value_tuples = tuple(
            map(tuple, present_label_value_list)
        )
        target_label_value_tuples = tuple(map(tuple, target_label_value_list))

        result = aggregator_func(
            x in present_label_value_tuples for x in target_label_value_tuples
        )
        return result
