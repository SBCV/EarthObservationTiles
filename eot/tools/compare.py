import sys
from eot.fusion.tile_comparison import compare_fusion_results_with_reference
from eot.tools import initialize_categories


def add_parser(subparser, formatter_class):
    parser = subparser.add_parser(
        "compare",
        help="Compute composite images",
        formatter_class=formatter_class,
    )

    inp = parser.add_argument_group("Inputs")
    inp.add_argument(
        "--label_idp",
        type=str,
        help="path to tiles labels directory [required for metrics filtering]",
    )
    inp.add_argument(
        "--mask_idp",
        type=str,
        help="path to tiles masks directory [required for metrics filtering)",
    )
    inp.add_argument(
        "--segmentation_categories",
        type=str,
        help="Categories",
    )
    inp.add_argument(
        "--comparison_categories",
        type=str,
        help="Categories",
    )

    output = parser.add_argument_group("Output")
    output.add_argument(
        "--geojson",
        action="store_true",
        help="output results as GeoJSON [optional for list mode]",
    )

    output_path = output.add_mutually_exclusive_group(required=True)
    output_path.add_argument(
        "--comparison_odp", type=str, help="output directory path"
    )

    if len(sys.argv) <= 2:
        parser.print_help(sys.stderr)
        sys.exit(1)

    parser.set_defaults(func=main)


def main(args):
    args = initialize_categories(
        args, attribute_name="segmentation_categories"
    )
    args = initialize_categories(args, attribute_name="comparison_categories")

    compare_fusion_results_with_reference(
        original_tile_idp=args.label_idp,
        fused_tile_idp=args.mask_idp,
        idp_uses_palette=True,
        comparison_tile_odp=args.comparison_odp,
        segmentation_categories=args.segmentation_categories.get_non_ignore_categories(),
        label_comparison_categories=args.comparison_categories,
    )
