import math
import random
from argparse import ArgumentParser
from collections import namedtuple
from glob import glob

from PIL import Image

Animation = namedtuple(
    "Animation", ("frame_width", "frame_height", "frame_count", "fps")
)

AnnealingParams = namedtuple(
    "AnnealingParams",
    (
        "initial_state",
        "mutate_state",
        "compute_energy",
        "temp_max",
        "temp_min",
        "cool_temp",
    ),
)


def simulate_annealing(params: AnnealingParams):
    current_state = params.initial_state
    current_energy = params.compute_energy(current_state)

    best_state = current_state
    best_energy = current_energy

    current_temp = params.temp_max

    while current_temp > params.temp_min:
        next_state = params.mutate_state(current_state)
        next_energy = params.compute_energy(next_state)

        if (
            next_energy < current_energy
            or math.exp((current_energy - next_energy) / current_temp) > random.random()
        ):
            current_state = next_state
            current_energy = next_energy

            if next_energy < best_energy:
                best_state = next_state
                best_energy = next_energy

        current_temp = params.cool_temp(current_temp)

    return best_state


Layout = namedtuple("AnnealingState", ("columns", "rows"))


def make_initial_state(animation: Animation) -> Layout:
    pixels = animation.frame_width * animation.frame_height * animation.frame_count
    side_length = math.sqrt(pixels)
    columns = int(side_length / animation.frame_width)
    rows = int(side_length / animation.frame_height)
    return Layout(columns=columns, rows=rows)


def state_valid(state: Layout, animation: Animation):
    if state.rows == 0 or state.columns == 0:
        return False

    width = state.columns * animation.frame_width
    height = state.rows * animation.frame_height

    if width > 11000 or height > 11000:
        return False

    return state.rows * state.columns <= animation.frame_count


mutations = (lambda x: x + 1, lambda x: x - 1)


def mutate_state(state: Layout, animation: Animation) -> Layout:
    mutation = random.choice(mutations)

    if random.randint(0, 1):
        next_state = Layout(columns=mutation(state.columns), rows=state.rows)
    else:
        next_state = Layout(columns=state.columns, rows=mutation(state.rows))

    if state_valid(next_state, animation):
        return next_state
    else:
        return state


def compute_energy(state: Layout, animation: Animation):
    return animation.frame_count - state.rows * state.columns


def compute_layout(animation: Animation) -> Layout:
    params = AnnealingParams(
        initial_state=make_initial_state(animation),
        mutate_state=lambda state: mutate_state(state, animation),
        compute_energy=lambda state: compute_energy(state, animation),
        temp_max=15,
        temp_min=0.001,
        cool_temp=lambda temp: temp - 0.001,
    )
    return simulate_annealing(params)


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

    packed_frame_count = layout.rows * layout.columns
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
