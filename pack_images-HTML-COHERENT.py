#!/usr/bin/env python3

from argparse import ArgumentParser
from collections import namedtuple
from glob import glob
from typing import Iterator

from PIL import Image

MAX_SIDE_LENGTH = 11000

Animation = namedtuple(
    "Animation", ("frame_width", "frame_height", "frame_count", "fps")
)

Layout = namedtuple("Layout", ("columns", "rows"))


def generate_layouts(animation: Animation) -> Iterator[Layout]:
    max_columns = int(MAX_SIDE_LENGTH / animation.frame_width)
    max_rows = int(MAX_SIDE_LENGTH / animation.frame_height)

    for columns in range(1, max_columns + 1):
        for rows in range(1, max_rows + 1):
            yield Layout(columns, rows)


def generate_sparse_layouts(animation: Animation) -> Iterator[Layout]:
    for layout in generate_layouts(animation):
        if layout.columns * layout.rows > animation.frame_count:
            yield layout


def generate_dense_layouts(animation: Animation) -> Iterator[Layout]:
    for layout in generate_layouts(animation):
        if layout.columns * layout.rows <= animation.frame_count:
            yield layout


def select_better_layout(
    animation: Animation, layout1: Layout, layout2: Layout
) -> Layout:
    layout1_frame_delta = abs(layout1.columns * layout1.rows - animation.frame_count)
    layout2_frame_delta = abs(layout2.columns * layout2.rows - animation.frame_count)

    if layout1_frame_delta < layout2_frame_delta:
        return layout1
    elif layout1_frame_delta > layout2_frame_delta:
        return layout2

    layout1_side_length_delta = abs(
        layout1.columns * animation.frame_width - layout1.rows * animation.frame_height
    )
    layout2_side_length_delta = abs(
        layout2.columns * animation.frame_width - layout2.rows * animation.frame_height
    )

    if layout1_side_length_delta < layout2_side_length_delta:
        return layout1
    elif layout1_side_length_delta > layout2_side_length_delta:
        return layout2
    else:
        return layout1


def compute_layout(animation: Animation, sparse=False) -> Layout:
    if sparse:
        possible_layouts = generate_sparse_layouts(animation)
    else:
        possible_layouts = generate_dense_layouts(animation)

    best_layout = None

    for layout in possible_layouts:
        if best_layout is None:
            best_layout = layout
        else:
            best_layout = select_better_layout(animation, best_layout, layout)

    return best_layout


def render_html(animation: Animation, layout: Layout):
    aspect_ratio = animation.frame_width / animation.frame_height

    if aspect_ratio <= 1024 / 613:
        return f"""\
<style>
    :root {{
        --aspect-ratio: calc({animation.frame_width} / {animation.frame_height});
        --fps: {animation.fps};
        --columns: {layout.columns};
        --rows: {layout.rows};
    }}

    img {{
        width: calc(100vh * var(--aspect-ratio) * var(--columns));
        height: calc(100vh * var(--rows));
    }}
    
    .clip {{
        margin: auto;
        height: 100vh;
        width: calc(100vh * var(--aspect-ratio));
        overflow: hidden;
    }}
    
    .scan-x {{
        animation: scan-x calc(1s * var(--columns) / var(--fps)) steps(var(--columns)) infinite;
    }}

    @keyframes scan-x {{
        0% {{
            transform: translateX(0);
        }}
        100% {{
            transform: translateX(-100%);
        }}
    }}

    .scan-y {{
        animation: scan-y calc(1s * var(--columns) * var(--rows) / var(--fps)) steps(var(--rows)) infinite;
    }}

    @keyframes scan-y {{
        0% {{
            transform: translateY(0);
        }}
        100% {{
            transform: translateY(-100%);
        }}
    }}
</style>
<div class="clip">
    <div class="scan-y">
        <img class="scan-x" src="<!-- INSERT IMAGE URL HERE -->"/>
    </div>
</div>"""
    else:
        return f"""\
<style>
    :root {{
        --aspect-ratio: calc({animation.frame_width} / {animation.frame_height});
        --fps: {animation.fps};
        --columns: {layout.columns};
        --rows: {layout.rows};
    }}

    img {{
        width: calc(100vw * var(--columns));
        height: calc(100vw * var(--rows) / var(--aspect-ratio));
    }}
    
    .clip {{
        height: calc(100vw / var(--aspect-ratio));
        width: 100vw;
        overflow: hidden;
    }}
    
    .center {{
        height: 100vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }}
    
    .scan-x {{
        animation: scan-x calc(1s * var(--columns) / var(--fps)) steps(var(--columns)) infinite;
    }}

    @keyframes scan-x {{
        0% {{
            transform: translateX(0);
        }}
        100% {{
            transform: translateX(-100%);
        }}
    }}

    .scan-y {{
        animation: scan-y calc(1s * var(--columns) * var(--rows) / var(--fps)) steps(var(--rows)) infinite;
    }}

    @keyframes scan-y {{
        0% {{
            transform: translateY(0);
        }}
        100% {{
            transform: translateY(-100%);
        }}
    }}
</style>

<div class="center">
    <div class="clip">
        <div class="scan-y">
            <img class="scan-x" src="<!-- INSERT IMAGE URL HERE -->"/>
        </div>
    </div>
</div>"""


def pack_animation(frame_glob, output_name, fps):
    image_paths = glob(frame_glob)
    frame_count = len(image_paths)

    if frame_count == 0:
        print("Pattern does not match any frames.")
        exit(1)

    with Image.open(image_paths[0]) as image:
        animation = Animation(*image.size, frame_count, fps)

    layout = compute_layout(animation)

    if layout is None:
        print("Couldn't find a suitable layout.")
        exit(1)

    packed_frame_count = layout.rows * layout.columns

    if packed_frame_count < frame_count:
        removed_frame_count = frame_count - packed_frame_count
        print(f"Shortening the sequence by {frame_count - packed_frame_count} frames.")

        sparse_layout = compute_layout(animation, sparse=True)
        if sparse_layout is not None:
            add_frame_count = sparse_layout.rows * sparse_layout.columns - frame_count
            print(
                f"Remove {removed_frame_count} frames",
                f"or add {add_frame_count} frames to prevent the sequence from being shortened.",
            )
        else:
            print(
                f"Remove {removed_frame_count} frames to prevent the sequence from being shortened."
            )

    packed_size = (
        layout.columns * animation.frame_width,
        layout.rows * animation.frame_height,
    )

    with Image.new("RGB", packed_size) as packed:
        for index, path in enumerate(image_paths[:packed_frame_count]):
            row = int(index / layout.columns)
            column = index % layout.columns

            x = column * animation.frame_width
            y = row * animation.frame_height

            with Image.open(path) as frame:
                region = frame.crop(
                    (0, 0, animation.frame_width, animation.frame_height)
                )
                packed.paste(
                    region,
                    (x, y, x + animation.frame_width, y + animation.frame_height),
                )

        packed.save(f"{output_name}.png")

    with open(f"{output_name}.html", "w") as f:
        f.write(render_html(animation, layout))


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "frame_glob",
        help="Glob pattern matching all frames of the animation.",
        type=str,
    )
    parser.add_argument(
        "output_name", help="Name of the output files.", type=str,
    )
    parser.add_argument(
        "fps", help="Frames per second.", type=float,
    )
    args = parser.parse_args()

    pack_animation(
        frame_glob=args.frame_glob, output_name=args.output_name, fps=args.fps
    )
