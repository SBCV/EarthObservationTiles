def compute_mask_values(mask_values, category_indices):
    if mask_values is not None:
        assert len(mask_values) == len(category_indices)
    else:
        # Do not confuse the category_index with the
        num_categories = len(category_indices)
        range_values = list(range(1, num_categories + 1))
        mask_values = [int(x / num_categories * 255) for x in range_values]
    return mask_values
