import pygame
import sys
import random
import math
import os
import io
import zipfile

try:
    from PIL import Image, ImageSequence
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

os.chdir(os.path.dirname(os.path.abspath(__file__)))

pygame.init()
pygame.font.init()

# ----------------------------------------------------
# 1. SETUP & CONSTANTS
# ----------------------------------------------------
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
WORLD_WIDTH, WORLD_HEIGHT = 2000, 1500
TILE_SIZE = 64

is_fullscreen = False
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SCALED)
pygame.display.set_caption("My RPG")
clock = pygame.time.Clock()

font = pygame.font.SysFont("courier", 11, bold=True)
font_small = pygame.font.SysFont("courier", 9, bold=True)


# ----------------------------------------------------
# DIALOGUE ALPHABET TEXTURES
# ----------------------------------------------------
# The ZIP contains exactly 52 letter textures:
#   0-25  = A-Z
#   26-51 = a-z
#
# The original PNGs are 1600x1600 and use transparent
# padding around each glyph. Keeping that full canvas when
# scaling them gives every letter the same 24x24 advance,
# which keeps the dialogue monospaced.
# ----------------------------------------------------

DIALOGUE_LETTER_SIZE = (24, 24)
DIALOGUE_LETTER_ADVANCE = 18
DIALOGUE_SPACE_ADVANCE = 18

alphabet_images = {}
alphabet_zip = None

alphabet_zip_candidates = [
    name
    for name in os.listdir(".")
    if (
        name.lower().endswith(".zip")
        and "alphabet" in name.lower()
    )
]

if not alphabet_zip_candidates:
    alphabet_zip_candidates = [
        name
        for name in os.listdir(".")
        if name.lower().endswith(".zip")
    ]

if alphabet_zip_candidates:

    alphabet_zip_path = alphabet_zip_candidates[0]

    try:

        alphabet_zip = zipfile.ZipFile(
            alphabet_zip_path,
            "r"
        )

        for index in range(52):

            filename = (
                f"pixil-frame-{index}.png"
            )

            try:

                image_data = alphabet_zip.read(
                    filename
                )

                source = pygame.image.load(
                    io.BytesIO(image_data)
                ).convert_alpha()

                # The original textures are 1600x1600.
                # Resize BEFORE creating the mask so we do not
                # process millions of pixels for every letter.
                source = pygame.transform.scale(
                    source,
                    DIALOGUE_LETTER_SIZE
                )

                # The source letters are black on transparent.
                # Turn the opaque pixels white first so the
                # dialogue color can be applied later.
                mask = pygame.mask.from_surface(
                    source
                )

                white_glyph = mask.to_surface(
                    setcolor=(255, 255, 255, 255),
                    unsetcolor=(0, 0, 0, 0)
                )

                alphabet_images[index] = white_glyph

            except Exception as e:

                print(
                    f"Could not load alphabet texture "
                    f"{filename}: {e}"
                )

        print(
            f"Loaded {len(alphabet_images)}/52 "
            f"dialogue alphabet textures from "
            f"{alphabet_zip_path}"
        )

        # We have copied all needed images into pygame surfaces,
        # so the ZIP no longer needs to stay open.
        alphabet_zip.close()
        alphabet_zip = None

    except Exception as e:

        print(
            f"Could not open dialogue alphabet ZIP: {e}"
        )

else:

    print(
        "No alphabet ZIP was found. "
        "Dialogue will use the fallback font."
    )


dialogue_glyph_cache = {}


def get_dialogue_glyph(char, color):

    if not alphabet_images:
        return None

    if char.isupper():

        index = (
            ord(char) - ord("A")
        )

    else:

        index = (
            26
            + ord(char) - ord("a")
        )

    if index < 0 or index >= 52:
        return None

    cache_key = (
        index,
        tuple(color)
    )

    if cache_key in dialogue_glyph_cache:
        return dialogue_glyph_cache[cache_key]

    base_glyph = alphabet_images.get(index)

    if base_glyph is None:
        return None

    glyph = base_glyph.copy()

    glyph.fill(
        (
            color[0],
            color[1],
            color[2],
            255
        ),
        special_flags=pygame.BLEND_RGBA_MULT
    )

    dialogue_glyph_cache[cache_key] = glyph

    return glyph


def dialogue_char_width(char, color=(255, 255, 255)):

    if char == " ":
        return DIALOGUE_SPACE_ADVANCE

    if (
        char.isalpha()
        and len(char) == 1
        and get_dialogue_glyph(char, color) is not None
    ):
        return DIALOGUE_LETTER_ADVANCE

    fallback = font.render(
        char,
        False,
        color
    )

    return fallback.get_width() * 2


def dialogue_text_width(text, color=(255, 255, 255)):

    return sum(
        dialogue_char_width(
            char,
            color
        )
        for char in text
    )


def render_dialogue_text(
    text,
    color=(255, 255, 255),
    fallback_font=font
):

    # If the ZIP could not be loaded, keep the game's
    # original text renderer as a safe fallback.
    if not alphabet_images:
        return render_pixel(
            text,
            color,
            fallback_font
        )

    width = max(
        1,
        dialogue_text_width(
            text,
            color
        )
    )

    height = DIALOGUE_LETTER_SIZE[1]

    surface = pygame.Surface(
        (width, height),
        pygame.SRCALPHA
    )

    x = 0

    for char in text:

        if char == " ":

            x += DIALOGUE_SPACE_ADVANCE
            continue

        glyph = get_dialogue_glyph(
            char,
            color
        )

        if glyph is not None:

            surface.blit(
                glyph,
                (x, 0)
            )

            x += DIALOGUE_LETTER_ADVANCE
            continue

        # Punctuation, numbers and other characters do not
        # have alphabet textures, so keep using the original
        # pixel font for those characters.
        fallback = fallback_font.render(
            char,
            False,
            color
        )

        if fallback.get_width() > 0:

            fallback = pygame.transform.scale(
                fallback,
                (
                    fallback.get_width() * 2,
                    fallback.get_height() * 2
                )
            )

            fallback_y = (
                DIALOGUE_LETTER_SIZE[1]
                - fallback.get_height()
            ) // 2

            surface.blit(
                fallback,
                (
                    x,
                    fallback_y
                )
            )

            x += fallback.get_width()

    return surface


def render_pixel(text, color, use_font=font, scale=2):
    surf = use_font.render(text, False, color)
    if scale != 1:
        surf = pygame.transform.scale(
            surf,
            (surf.get_width() * scale, surf.get_height() * scale)
        )
    return surf


def draw_wrapped_text(
    surface,
    text,
    pos,
    max_width,
    color=(255, 255, 255),
    use_font=font,
    line_spacing=6,
    scale=2
):
    # Dialogue uses the custom 52-image alphabet.
    # The old font remains available for punctuation/numbers.
    words = text.split(" ")
    lines = []
    current_line = ""

    for word in words:

        test_line = (
            word
            if not current_line
            else current_line + " " + word
        )

        if (
            dialogue_text_width(
                test_line,
                color
            )
            <= max_width
        ):

            current_line = test_line

        else:

            if current_line:
                lines.append(
                    current_line
                )

            current_line = word

    if current_line:
        lines.append(
            current_line
        )

    x, y = pos

    for line in lines:

        rendered = render_dialogue_text(
            line,
            color,
            use_font
        )

        surface.blit(
            rendered,
            (x, y)
        )

        y += (
            rendered.get_height()
            + line_spacing
        )


PLAYER_SIZE = (128, 128)

# Game States
STATE_OVERWORLD = "OVERWORLD"
STATE_BATTLE = "BATTLE"
STATE_DEATH = "DEATH"

game_state = STATE_OVERWORLD

# ----------------------------------------------------
# 2. LOAD SPRITES & ANIMATIONS
# ----------------------------------------------------

# Grass
grass_tiles = []

for i in range(1, 4):
    loaded = False

    for ext in [
        ".png",
        ".webp",
        ".jpg",
        ".jpeg",
        ".PNG",
        ".WEBP"
    ]:
        filename = f"grass_tile{i}{ext}"

        if os.path.exists(filename):
            try:
                raw_tile = pygame.image.load(filename).convert_alpha()

                scaled_tile = pygame.transform.scale(
                    raw_tile,
                    (TILE_SIZE, TILE_SIZE)
                )

                grass_tiles.append(scaled_tile)
                loaded = True
                break

            except pygame.error:
                pass

    if not loaded:
        fallback_surf = pygame.Surface(
            (TILE_SIZE, TILE_SIZE)
        )

        fallback_surf.fill(
            (
                40 + i * 15,
                100 + i * 10,
                40
            )
        )

        grass_tiles.append(fallback_surf)


# ----------------------------------------------------
# WORLD BACKGROUND (SKY + CLOUDS)
# ----------------------------------------------------
# One big backdrop with the sky and clouds already painted
# into it. It's loaded once and pre-scaled to exactly cover
# the world, so it can just be drawn at world position (0, 0)
# every frame instead of placing lots of little cloud sprites.

background_sprite = None

for ext in [
    "",
    ".png",
    ".webp",
    ".jpg",
    ".jpeg",
    ".PNG",
    ".WEBP",
    ".JPG",
    ".JPEG"
]:

    background_file = "backround_clouds" + ext

    if os.path.exists(background_file) and os.path.isfile(background_file):

        try:
            raw_background = pygame.image.load(
                background_file
            ).convert()

            background_sprite = pygame.transform.smoothscale(
                raw_background,
                (WORLD_WIDTH, WORLD_HEIGHT)
            )

            print(
                f"Loaded background texture: "
                f"{raw_background.get_width()}x"
                f"{raw_background.get_height()} -> "
                f"{WORLD_WIDTH}x{WORLD_HEIGHT}"
            )

            break

        except pygame.error as e:
            print(f"Background load error: {e}")


GRID_COLS = math.ceil(
    WORLD_WIDTH / TILE_SIZE
)

GRID_ROWS = math.ceil(
    WORLD_HEIGHT / TILE_SIZE
)


tile_map = []

for row in range(GRID_ROWS):

    row_tiles = []

    for col in range(GRID_COLS):
        row_tiles.append(
            random.randint(
                0,
                len(grass_tiles) - 1
            )
        )

    tile_map.append(row_tiles)


# ----------------------------------------------------
# PLAYER
# ----------------------------------------------------

has_idle = False
player_idle_right = None
player_idle_left = None

for filename in [
    "player_idle.png",
    "player_idle.png.png",
    "player_idle.PNG",
    "player_idle.webp"
]:

    if os.path.exists(filename):

        try:
            raw = pygame.image.load(
                filename
            ).convert_alpha()

            player_idle_right = pygame.transform.scale(
                raw,
                PLAYER_SIZE
            )

            player_idle_left = pygame.transform.flip(
                player_idle_right,
                True,
                False
            )

            has_idle = True
            break

        except pygame.error:
            pass


# ----------------------------------------------------
# WALK ANIMATION
# ----------------------------------------------------

walk_frames_right = []
walk_frames_left = []
has_walk = False


def load_animation_frames(filepath, size):

    frames = []

    if HAS_PIL:

        try:

            pil_img = Image.open(filepath)

            for frame in ImageSequence.Iterator(pil_img):

                frame_rgba = frame.convert("RGBA")

                # Resize before cleaning pixels. This keeps the
                # expensive pixel loop at the actual game size
                # instead of the source animation's full size.
                frame_rgba = frame_rgba.resize(
                    size,
                    Image.Resampling.NEAREST
                    if hasattr(Image, "Resampling")
                    else Image.NEAREST
                )

                pixel_data = frame_rgba.getdata()
                cleaned_pixels = []

                for r, g, b, a in pixel_data:

                    if (
                        r > 235
                        and g > 235
                        and b > 235
                    ) or a < 10:

                        cleaned_pixels.append(
                            (0, 0, 0, 0)
                        )

                    else:

                        cleaned_pixels.append(
                            (r, g, b, a)
                        )

                clean_frame = Image.new(
                    "RGBA",
                    frame_rgba.size
                )

                clean_frame.putdata(
                    cleaned_pixels
                )

                raw_bytes = clean_frame.tobytes()

                py_surface = pygame.image.fromstring(
                    raw_bytes,
                    clean_frame.size,
                    "RGBA"
                ).convert_alpha()

                frames.append(py_surface)

        except Exception as e:
            print(
                f"Animation load error: {e}"
            )

    else:

        try:

            raw = pygame.image.load(
                filepath
            ).convert_alpha()

            frames.append(
                pygame.transform.scale(
                    raw,
                    size
                )
            )

        except pygame.error:
            pass

    return frames


walk_filename = None

for name in [
    "player_walk.webp",
    "player_walk.gif",
    "player_walk.webp.webp",
    "player_walk.gif.gif"
]:

    if os.path.exists(name):
        walk_filename = name
        break


if walk_filename:

    walk_frames_right = load_animation_frames(
        walk_filename,
        PLAYER_SIZE
    )

    if walk_frames_right:

        walk_frames_left = [
            pygame.transform.flip(
                f,
                True,
                False
            )
            for f in walk_frames_right
        ]

        has_walk = True


anim_frame_idx = 0
anim_timer = 0
ANIM_SPEED = 8
facing_right = True


# ----------------------------------------------------
# SOUL TEXTURE
# ----------------------------------------------------

SOUL_SIZE = (68, 68)

soul_sprite = None

for ext in [
    "",
    ".jpeg",
    ".jpg",
    ".png",
    ".webp",
    ".JPEG",
    ".JPG",
    ".PNG",
    ".WEBP"
]:

    soul_file = "soul" + ext

    if os.path.exists(soul_file) and os.path.isfile(soul_file):

        try:

            raw_soul = pygame.image.load(
                soul_file
            ).convert_alpha()

            # The soul is displayed at 68x68, so resize it first.
            # The hitbox is NOT affected by this; it remains 12x12.
            raw_soul = pygame.transform.scale(
                raw_soul,
                SOUL_SIZE
            )

            soul_surf = pygame.Surface(
                SOUL_SIZE,
                pygame.SRCALPHA
            )

            soul_surf.blit(
                raw_soul,
                (0, 0)
            )

            for x in range(
                SOUL_SIZE[0]
            ):

                for y in range(
                    soul_surf.get_height()
                ):

                    r, g, b, _ = soul_surf.get_at(
                        (x, y)
                    )

                    if (
                        (
                            r > 210
                            and g > 210
                            and b > 210
                        )
                        or (
                            r < 45
                            and g < 45
                            and b < 45
                        )
                    ):

                        soul_surf.set_at(
                            (x, y),
                            (0, 0, 0, 0)
                        )

            soul_sprite = soul_surf

            break

        except pygame.error:
            pass


# ----------------------------------------------------
# CHEST
# ----------------------------------------------------

chest_closed_sprite = None
chest_open_sprite = None

for ext in [
    "",
    ".png",
    ".webp",
    ".jpg",
    ".jpeg",
    ".PNG",
    ".WEBP"
]:

    if (
        not chest_closed_sprite
        and os.path.exists(
            "chest_closed" + ext
        )
    ):

        try:

            chest_closed_sprite = pygame.transform.scale(
                pygame.image.load(
                    "chest_closed" + ext
                ).convert_alpha(),
                (80, 80)
            )

        except pygame.error:
            pass


    if (
        not chest_open_sprite
        and os.path.exists(
            "chest_open" + ext
        )
    ):

        try:

            chest_open_sprite = pygame.transform.scale(
                pygame.image.load(
                    "chest_open" + ext
                ).convert_alpha(),
                (80, 80)
            )

        except pygame.error:
            pass


# ----------------------------------------------------
# ENEMY SPRITE
# ----------------------------------------------------

enemy_sprite_battle = None
enemy_sprite_overworld = None
has_enemy_sprite = False

for ext in [
    "",
    ".png",
    ".webp",
    ".jpg",
    ".jpeg",
    ".gif",
    ".PNG",
    ".WEBP"
]:

    enemy_file = "enemy" + ext

    if (
        os.path.exists(enemy_file)
        and os.path.isfile(enemy_file)
    ):

        try:

            raw_enemy = pygame.image.load(
                enemy_file
            ).convert_alpha()

            enemy_sprite_battle = pygame.transform.scale(
                raw_enemy,
                (128, 128)
            )

            enemy_sprite_overworld = pygame.transform.scale(
                raw_enemy,
                (64, 64)
            )

            has_enemy_sprite = True
            break

        except pygame.error:
            pass


# ----------------------------------------------------
# MID SIR
# ----------------------------------------------------

mid_sprite_battle = None
mid_sprite_overworld = None
has_mid_sprite = False

for base_name in [
    "mid_sir",
    "enemy_mid"
]:

    for ext in [
        "",
        ".png",
        ".webp",
        ".jpg",
        ".jpeg",
        ".gif",
        ".PNG",
        ".WEBP"
    ]:

        mid_file = base_name + ext

        if (
            os.path.exists(mid_file)
            and os.path.isfile(mid_file)
        ):

            try:

                raw_mid = pygame.image.load(
                    mid_file
                ).convert_alpha()

                mid_sprite_battle = pygame.transform.scale(
                    raw_mid,
                    (128, 128)
                )

                mid_sprite_overworld = pygame.transform.scale(
                    raw_mid,
                    (64, 64)
                )

                has_mid_sprite = True
                break

            except pygame.error:
                pass

    if has_mid_sprite:
        break


# ----------------------------------------------------
# EVIL SIR
# ----------------------------------------------------

evil_sprite_battle = None
evil_sprite_overworld = None
has_evil_sprite = False

for base_name in [
    "evil_sir",
    "enemy_evil"
]:

    for ext in [
        "",
        ".png",
        ".webp",
        ".jpg",
        ".jpeg",
        ".gif",
        ".PNG",
        ".WEBP"
    ]:

        evil_file = base_name + ext

        if (
            os.path.exists(evil_file)
            and os.path.isfile(evil_file)
        ):

            try:

                raw_evil = pygame.image.load(
                    evil_file
                ).convert_alpha()

                evil_sprite_battle = pygame.transform.scale(
                    raw_evil,
                    (140, 140)
                )

                evil_sprite_overworld = pygame.transform.scale(
                    raw_evil,
                    (64, 64)
                )

                has_evil_sprite = True
                break

            except pygame.error:
                pass

    if has_evil_sprite:
        break


# ----------------------------------------------------
# HARD SIR
# ----------------------------------------------------

hard_sprite_battle = None
hard_sprite_overworld = None
has_hard_sprite = False

for ext in [
    "",
    ".png",
    ".webp",
    ".jpg",
    ".jpeg",
    ".gif",
    ".PNG",
    ".WEBP"
]:

    hard_file = "hard_sir" + ext

    if (
        os.path.exists(hard_file)
        and os.path.isfile(hard_file)
    ):

        try:

            raw_hard = pygame.image.load(
                hard_file
            ).convert_alpha()

            hard_sprite_battle = pygame.transform.scale(
                raw_hard,
                (150, 150)
            )

            hard_sprite_overworld = pygame.transform.scale(
                raw_hard,
                (64, 64)
            )

            has_hard_sprite = True
            break

        except pygame.error:
            pass


# ----------------------------------------------------
# PRACTICE DUMMY
# ----------------------------------------------------

dummy_sprite_battle = None
dummy_sprite_overworld = None
has_dummy_sprite = False

for ext in [
    "",
    ".png",
    ".webp",
    ".jpg",
    ".jpeg",
    ".gif",
    ".PNG",
    ".WEBP"
]:

    dummy_file = "enemy_dummy" + ext

    if (
        os.path.exists(dummy_file)
        and os.path.isfile(dummy_file)
    ):

        try:

            raw_dummy = pygame.image.load(
                dummy_file
            ).convert_alpha()

            dummy_sprite_battle = pygame.transform.scale(
                raw_dummy,
                (192, 192)
            )

            dummy_sprite_overworld = pygame.transform.scale(
                raw_dummy,
                (96, 96)
            )

            has_dummy_sprite = True
            break

        except pygame.error:
            pass


# ----------------------------------------------------
# FOREST SIGN
# ----------------------------------------------------

sign_sprite = None
has_sign_sprite = False

possible_sign_paths = [
    "4est_sign",
    "4est_sign.png",
    "4est_sign.webp",
    "4est_sign.jpg",
    "4est_sign.jpeg"
]

for target in possible_sign_paths:

    if (
        os.path.exists(target)
        and os.path.isfile(target)
    ):

        try:

            raw_sign = pygame.image.load(
                target
            ).convert_alpha()

            sign_sprite = pygame.transform.scale(
                raw_sign,
                (128, 96)
            )

            has_sign_sprite = True
            break

        except pygame.error:
            pass


# ----------------------------------------------------
# ADVENTURER SIR NPC
# ----------------------------------------------------

NPC_SPRITE_SIZE = (144, 144)
NPC_ANIM_SPEED = 24

npc_anim_frames = []
has_talking_npc_sprite = False

for ext in [
    ".webp",
    ".gif",
    ".png",
    "",
    ".jpg",
    ".jpeg",
    ".WEBP",
    ".GIF"
]:

    npc_file = "adventurer_sir_npc" + ext

    if (
        os.path.exists(npc_file)
        and os.path.isfile(npc_file)
    ):

        npc_anim_frames = load_animation_frames(
            npc_file,
            NPC_SPRITE_SIZE
        )

        if npc_anim_frames:
            has_talking_npc_sprite = True
            break


npc_anim_idx = 0
npc_anim_timer = 0


# ----------------------------------------------------
# 3. OVERWORLD & DIALOGUE VARIABLES
# ----------------------------------------------------

player = pygame.Rect(
    400,
    300,
    64,
    64
)

player_speed = 5
player_hp = 50
player_max_hp = 50
player_xp = 0
player_bucks = 0
is_moving = False


sign_npc = pygame.Rect(
    300,
    350,
    128,
    96
)

# Smaller collision box so the player can walk right up next to
# the signboard/legs instead of bumping into the full sprite bounds.
# Sprite drawing and the "read sign" trigger zone still use sign_npc.
sign_hitbox = sign_npc.inflate(-64, -48)

chest_npc = pygame.Rect(
    450,
    400,
    80,
    80
)

chest_opened = False


# Floor and walls aligned to TILE_SIZE (64) so they line up cleanly with the grass tiles
FLOOR_AREA = pygame.Rect(
    0,
    192,          # 3 * 64
    WORLD_WIDTH,
    384           # 6 * 64  → ends at 576
)


TOP_WALL_RECT = pygame.Rect(0, 160, WORLD_WIDTH, 32)
BOTTOM_WALL_RECT = pygame.Rect(0, 576, WORLD_WIDTH, 32)

# The top wall stays as a collision barrier, but is invisible.
# The bottom wall uses the bottom_walls texture for its appearance.
walls = [
    TOP_WALL_RECT,
    BOTTOM_WALL_RECT,
    sign_hitbox,
    chest_npc
]


# ----------------------------------------------------
# BOTTOM WALL TEXTURE
# ----------------------------------------------------

bottom_wall_texture = None
bottom_wall_bottom_texture = None

for ext in [
    "",
    ".png",
    ".webp",
    ".jpg",
    ".jpeg",
    ".PNG",
    ".WEBP",
    ".JPG",
    ".JPEG"
]:

    bottom_wall_file = "bottom_walls" + ext

    if os.path.exists(bottom_wall_file) and os.path.isfile(bottom_wall_file):

        try:
            raw_bottom_wall = pygame.image.load(
                bottom_wall_file
            ).convert_alpha()

            # Scale one wall tile to the same width as a floor tile,
            # then repeat it across the entire bottom wall.
            # Make the wall tile a little taller visually while
            # keeping the actual wall collision rectangle unchanged.
            BOTTOM_WALL_TEXTURE_HEIGHT = 48
            bottom_wall_tile = pygame.transform.scale(
                raw_bottom_wall,
                (TILE_SIZE, BOTTOM_WALL_TEXTURE_HEIGHT)
            )

            # Pre-build the tiled wall once so we do not have to scale
            # or recreate tiles every frame.
            bottom_wall_texture = pygame.Surface(
                (BOTTOM_WALL_RECT.width, BOTTOM_WALL_TEXTURE_HEIGHT),
                pygame.SRCALPHA
            )

            for tile_x in range(0, BOTTOM_WALL_RECT.width, TILE_SIZE):
                bottom_wall_texture.blit(
                    bottom_wall_tile,
                    (tile_x, 0)
                )

            print(
                f"Loaded and tiled bottom wall texture: {bottom_wall_file}"
            )
            break

        except pygame.error as e:
            print(f"Bottom wall texture load error: {e}")

# ----------------------------------------------------
# BOTTOM WALL BOTTOM TEXTURE
# ----------------------------------------------------

for ext in [
    "",
    ".png",
    ".webp",
    ".jpg",
    ".jpeg",
    ".PNG",
    ".WEBP",
    ".JPG",
    ".JPEG"
]:

    bottom_wall_bottom_file = "bottom_walls_bottom" + ext

    if os.path.exists(bottom_wall_bottom_file) and os.path.isfile(bottom_wall_bottom_file):

        try:
            raw_bottom_wall_bottom = pygame.image.load(
                bottom_wall_bottom_file
            ).convert_alpha()

            bottom_wall_bottom_tile = pygame.transform.scale(
                raw_bottom_wall_bottom,
                (TILE_SIZE, TILE_SIZE)
            )

            # Pre-build the second tiled row once.
            bottom_wall_bottom_texture = pygame.Surface(
                (BOTTOM_WALL_RECT.width, TILE_SIZE),
                pygame.SRCALPHA
            )

            for tile_x in range(0, BOTTOM_WALL_RECT.width, TILE_SIZE):
                bottom_wall_bottom_texture.blit(
                    bottom_wall_bottom_tile,
                    (tile_x, 0)
                )

            print(
                f"Loaded and tiled bottom wall bottom texture: {bottom_wall_bottom_file}"
            )
            break

        except pygame.error as e:
            print(f"Bottom wall bottom texture load error: {e}")

talking_npc = pygame.Rect(
    500,
    300,
    64,
    64
)

in_dialogue = False
npc_step = "HELLO"
npc_choice = 0


enemy_npc = pygame.Rect(
    800,
    300,
    64,
    64
)

enemy_defeated = False


duo_enemy_npc = pygame.Rect(
    1300,
    300,
    64,
    64
)

duo_enemy_defeated = False


evil_npc = pygame.Rect(
    1100,
    300,
    64,
    64
)

evil_defeated = False


hard_npc = pygame.Rect(
    1750,
    350,
    64,
    64
)

hard_defeated = False


dummy_npc = pygame.Rect(
    650,
    300,
    64,
    64
)

dummy_defeated = False


current_enemy = "BAD_SIR"


# ----------------------------------------------------
# ITEM BUTTON TEXTURES
# ----------------------------------------------------

def load_named_texture(base_name):
    for ext in [".png", ".webp", ".jpg", ".jpeg", ".PNG", ".WEBP"]:
        filename = base_name + ext
        if os.path.exists(filename):
            try:
                return pygame.image.load(filename).convert_alpha()
            except pygame.error:
                pass
    return None


item_button_texture = load_named_texture("item_button")
item_button_hovered_texture = load_named_texture("item_button_hovered")
act_button_texture = load_named_texture("act_button")
act_button_hovered_texture = load_named_texture("act_button_hovered")
spare_button_texture = load_named_texture("spare_button")
spare_button_hovered_texture = load_named_texture("spare_button_hovered")
ready_spare_button_texture = load_named_texture("readdy_spare_button")
ready_spare_button_hovered_texture = load_named_texture("ready_spare_button_hovered")
fight_button_texture = load_named_texture("fight_button")
fight_button_hovered_texture = load_named_texture("fight_button_hovered")
fight_bar_texture = load_named_texture("fight_bar")
fight_landing_texture = load_named_texture("fight_landing_thing")


def draw_item_button_texture(surface, texture, center, height):
    if texture is None:
        return False

    # Preserve the texture's original aspect ratio so it never gets squished.
    ratio = texture.get_width() / texture.get_height()
    width = max(1, int(height * ratio))
    scaled = pygame.transform.scale(texture, (width, height))
    rect = scaled.get_rect(center=center)
    surface.blit(scaled, rect)
    return True



# The duo battle picks 2 different enemies each time it starts.
duo_enemy_types = ["BAD_SIR", "MID_SIR"]

death_alpha = 0


# ----------------------------------------------------
# 4. BATTLE VARIABLES
# ----------------------------------------------------

battle_substate = "MENU"

menu_index = 0
act_index = 0
item_index = 0
target_index = 0
target_action = "FIGHT"

duo_enemy_hp = [160, 160]
duo_enemy_mercy = [0, 0]
duo_enemy_defeated = [False, False]

enemy_hp = 200
enemy_max_hp = 200
enemy_mercy = 0
acts_done = 0

battle_text = "Bad Sir Blocks The Way!"


RANDOM_FLAVOR_TEXTS = {

    "BAD_SIR": [
        "Smells like bagel.",
        "Scientists say that you shall act instead of fighting.",
        "Bleh"
    ],

    "DUO_BAD_SIRS": [
        "Smells like chez puffs.",
        "Double the Sirs, double the trouble.",
        "[FUN FACT]: There are 2 enemies now."
    ],

    "PRACTICE_DUMMY": [
        "Practice Dummy stands patiently.",
        "It doesn't seem to mind your presence.",
        "Practice Dummy looks content doing nothing."
    ],

    "EVIL_SIR": [
        "TIP: try not to die",
        "The air around you feels freezing cold.",
        "Evil sir glooms in the.. light?",
        "Smells like Waxed Weathered Cut Copper Stairs."
    ],

    "HARD_SIR": [
        "A little bird told me that the brown guy over there is thinking something complicated.",
        "The battle box feels strangely unstable.",
        "Scientists say that brown equals hard.",
        "Smells like dirt. Because you know its brown-"
    ]
}


attack_bar_pos = 0
attack_bar_dir = 7
fight_prep_timer = 0


arena = pygame.Rect(
    280,
    240,
    240,
    150
)

SOUL_HITBOX_SIZE = (12, 12)

soul = pygame.Rect(
    386,
    301,
    SOUL_HITBOX_SIZE[0],
    SOUL_HITBOX_SIZE[1]
)

soul_speed = 4

bullets = []

dodge_timer = 0
dodge_prep_timer = 0
invincible_timer = 0

current_attack_type = 1


# ----------------------------------------------------
# HARD SIR EFFECTS
# ----------------------------------------------------

ARENA_DEFAULT = (
    280,
    240,
    240,
    150
)

hard_move_x = 0
hard_move_y = 0
hard_attack_clock = 0
hard_rotation = 0.0


items = [
    "Medkit (+30 HP)"
]


# ----------------------------------------------------
# DRAW HELPERS
# ----------------------------------------------------

def draw_pixel_box(
    surface,
    rect,
    border_color=(255, 255, 255),
    fill_color=(0, 0, 0),
    border_width=4
):

    pygame.draw.rect(
        surface,
        fill_color,
        rect
    )

    pygame.draw.rect(
        surface,
        border_color,
        rect,
        border_width
    )

    inner_rect = rect.inflate(
        -border_width * 2,
        -border_width * 2
    )

    pygame.draw.rect(
        surface,
        (0, 0, 0),
        inner_rect,
        2
    )


# ----------------------------------------------------
# ATTACK SETUP
# ----------------------------------------------------

def setup_enemy_attack(attack_type):

    global bullets

    bullets = []

    if current_enemy == "PRACTICE_DUMMY":
        return


    # ------------------------------------------------
    # BAD SIR
    # ------------------------------------------------

    if current_enemy == "BAD_SIR":

        if attack_type == 1:

            for i in range(6):

                x_pos = (
                    arena.left
                    + 20
                    + i * 35
                )

                bullets.append({
                    "rect": pygame.Rect(
                        x_pos,
                        arena.top + 10,
                        10,
                        14
                    ),
                    "vx": 0,
                    "vy": 3.5,
                    "type": "rain",
                    "color_type": "normal",
                    "dmg": 3
                })


        elif attack_type == 2:

            corners = [
                (
                    arena.left + 10,
                    arena.top + 10
                ),
                (
                    arena.right - 20,
                    arena.top + 10
                ),
                (
                    arena.left + 10,
                    arena.bottom - 20
                ),
                (
                    arena.right - 20,
                    arena.bottom - 20
                )
            ]

            for cx, cy in corners:

                angle = math.atan2(
                    soul.centery - cy,
                    soul.centerx - cx
                )

                vx = math.cos(angle) * 3.8
                vy = math.sin(angle) * 3.8

                bullets.append({
                    "rect": pygame.Rect(
                        cx,
                        cy,
                        12,
                        12
                    ),
                    "vx": vx,
                    "vy": vy,
                    "type": "aimed",
                    "color_type": "normal",
                    "dmg": 3
                })


        elif attack_type == 3:

            bullets = [

                {
                    "rect": pygame.Rect(
                        arena.left + 20,
                        arena.top + 20,
                        12,
                        12
                    ),
                    "vx": 4,
                    "vy": 3,
                    "type": "bounce",
                    "color_type": "normal",
                    "dmg": 3
                },

                {
                    "rect": pygame.Rect(
                        arena.right - 30,
                        arena.bottom - 30,
                        12,
                        12
                    ),
                    "vx": -3,
                    "vy": -4,
                    "type": "bounce",
                    "color_type": "normal",
                    "dmg": 3
                },

                {
                    "rect": pygame.Rect(
                        arena.left + 100,
                        arena.top + 20,
                        12,
                        12
                    ),
                    "vx": 2,
                    "vy": 4,
                    "type": "bounce",
                    "color_type": "normal",
                    "dmg": 3
                }
            ]


    # ------------------------------------------------
    # DUO BAD SIRS
    # ------------------------------------------------

    elif current_enemy == "DUO_BAD_SIRS":

        if attack_type == 1:

            for i in range(4):

                x_pos = (
                    arena.left
                    + 25
                    + i * 50
                )

                bullets.append({
                    "rect": pygame.Rect(
                        x_pos,
                        arena.top + 10,
                        10,
                        14
                    ),
                    "vx": 0,
                    "vy": 3.2,
                    "type": "rain",
                    "color_type": "normal",
                    "dmg": 4
                })

            corners = [
                (
                    arena.left + 10,
                    arena.top + 10
                ),
                (
                    arena.right - 20,
                    arena.bottom - 20
                )
            ]

            for cx, cy in corners:

                angle = math.atan2(
                    soul.centery - cy,
                    soul.centerx - cx
                )

                bullets.append({
                    "rect": pygame.Rect(
                        cx,
                        cy,
                        12,
                        12
                    ),
                    "vx": math.cos(angle) * 3.5,
                    "vy": math.sin(angle) * 3.5,
                    "type": "aimed",
                    "color_type": "normal",
                    "dmg": 4
                })


        elif attack_type == 2:

            bullets.append({
                "rect": pygame.Rect(
                    arena.left + 20,
                    arena.top + 20,
                    12,
                    12
                ),
                "vx": 3.5,
                "vy": 3.5,
                "type": "bounce",
                "color_type": "normal",
                "dmg": 4
            })

            bullets.append({
                "rect": pygame.Rect(
                    arena.right - 20,
                    arena.top + 80,
                    12,
                    12
                ),
                "vx": -3.5,
                "vy": -3.0,
                "type": "bounce",
                "color_type": "normal",
                "dmg": 4
            })

            bullets.append({
                "rect": pygame.Rect(
                    arena.left - 20,
                    arena.top + 35,
                    28,
                    14
                ),
                "vx": 3.8,
                "vy": 0,
                "type": "color_wave",
                "color_type": "blue",
                "dmg": 5
            })

            bullets.append({
                "rect": pygame.Rect(
                    arena.right + 20,
                    arena.top + 95,
                    28,
                    14
                ),
                "vx": -3.8,
                "vy": 0,
                "type": "color_wave",
                "color_type": "orange",
                "dmg": 5
            })


        elif attack_type == 3:

            bullets.append({
                "rect": pygame.Rect(
                    arena.left,
                    arena.top + 45,
                    arena.width,
                    40
                ),
                "timer": 25,
                "active": 25,
                "type": "laser",
                "dmg": 8
            })

            radius = 160
            num_bullets = 10

            for i in range(num_bullets):

                angle = (
                    2 * math.pi
                    / num_bullets
                    * i
                )

                bx = (
                    arena.centerx
                    + math.cos(angle) * radius
                )

                by = (
                    arena.centery
                    + math.sin(angle) * radius
                )

                bullets.append({
                    "rect": pygame.Rect(
                        bx - 6,
                        by - 6,
                        12,
                        12
                    ),
                    "vx": -math.cos(angle) * 1.8,
                    "vy": -math.sin(angle) * 1.8,
                    "type": "ring",
                    "color_type": "normal",
                    "dmg": 4
                })


    # ------------------------------------------------
    # EVIL SIR
    # ------------------------------------------------

    elif current_enemy == "EVIL_SIR":

        if attack_type == 1:

            for wave in range(2):

                radius = (
                    170
                    + wave * 110
                )

                gap_angle = random.uniform(
                    0,
                    2 * math.pi
                )

                num_bullets = 15

                for i in range(num_bullets):

                    angle = (
                        2 * math.pi
                        / num_bullets
                        * i
                    )

                    if abs(
                        (
                            angle
                            - gap_angle
                            + math.pi
                        )
                        % (2 * math.pi)
                        - math.pi
                    ) < 0.4:
                        continue

                    bx = (
                        arena.centerx
                        + math.cos(angle)
                        * radius
                    )

                    by = (
                        arena.centery
                        + math.sin(angle)
                        * radius
                    )

                    speed = (
                        2.0
                        - wave * 0.3
                    )

                    bullets.append({
                        "rect": pygame.Rect(
                            bx - 6,
                            by - 6,
                            12,
                            12
                        ),
                        "vx": -math.cos(angle) * speed,
                        "vy": -math.sin(angle) * speed,
                        "type": "ring",
                        "color_type": "normal",
                        "dmg": 8
                    })


        elif attack_type == 2:

            for i in range(5):

                y_pos = (
                    arena.top
                    + 12
                    + i * 26
                )

                is_blue = (
                    i % 2 == 0
                )

                bullet_color = (
                    "blue"
                    if is_blue
                    else "orange"
                )

                speed = (
                    3.8
                    if is_blue
                    else -3.8
                )

                start_x = (
                    arena.left - 20
                    if speed > 0
                    else arena.right + 20
                )

                for j in range(3):

                    bullets.append({
                        "rect": pygame.Rect(
                            start_x
                            - j * 60
                            * (
                                1
                                if speed > 0
                                else -1
                            ),
                            y_pos,
                            28,
                            14
                        ),
                        "vx": speed,
                        "vy": 0,
                        "type": "color_wave",
                        "color_type": bullet_color,
                        "dmg": 8
                    })


        elif attack_type == 3:

            for ring in range(3):

                angle_offset = (
                    ring * 0.35
                )

                radius = (
                    180
                    + ring * 60
                )

                for arm in range(4):

                    angle = (
                        angle_offset
                        + arm * (math.pi / 2)
                    )

                    bx = (
                        arena.centerx
                        + math.cos(angle)
                        * radius
                    )

                    by = (
                        arena.centery
                        + math.sin(angle)
                        * radius
                    )

                    bullets.append({
                        "rect": pygame.Rect(
                            bx - 6,
                            by - 6,
                            12,
                            12
                        ),
                        "vx": -math.cos(angle) * 2.5,
                        "vy": -math.sin(angle) * 2.5,
                        "type": "spiral",
                        "color_type": "normal",
                        "dmg": 8
                    })


        elif attack_type == 4:

            bullets = [

                {
                    "rect": pygame.Rect(
                        arena.left,
                        arena.top + 8,
                        arena.width,
                        45
                    ),
                    "timer": 20,
                    "active": 20,
                    "type": "laser",
                    "dmg": 15
                },

                {
                    "rect": pygame.Rect(
                        arena.left + 15,
                        arena.top,
                        45,
                        arena.height
                    ),
                    "timer": 20,
                    "active": 20,
                    "type": "laser",
                    "dmg": 15
                },

                {
                    "rect": pygame.Rect(
                        arena.left,
                        arena.bottom - 53,
                        arena.width,
                        45
                    ),
                    "timer": 50,
                    "active": 20,
                    "type": "laser",
                    "dmg": 15
                },

                {
                    "rect": pygame.Rect(
                        arena.left + arena.width - 60,
                        arena.top,
                        45,
                        arena.height
                    ),
                    "timer": 50,
                    "active": 20,
                    "type": "laser",
                    "dmg": 15
                },

                {
                    "rect": pygame.Rect(
                        arena.left,
                        arena.top + 50,
                        arena.width,
                        50
                    ),
                    "timer": 80,
                    "active": 25,
                    "type": "laser",
                    "dmg": 15
                },

                {
                    "rect": pygame.Rect(
                        arena.left
                        + arena.width // 2
                        - 25,
                        arena.top,
                        50,
                        arena.height
                    ),
                    "timer": 80,
                    "active": 25,
                    "type": "laser",
                    "dmg": 15
                }
            ]


    # ------------------------------------------------
    # HARD SIR
    # ------------------------------------------------

    elif current_enemy == "HARD_SIR":

        # Hard Sir's attacks are deliberately predictable and contained.
        if attack_type == 1:

            # Five slow falling projectiles with fixed spacing.
            for i in range(5):
                x = arena.left + 30 + i * 45
                bullets.append({
                    "rect": pygame.Rect(x, arena.top - 16, 12, 12),
                    "vx": 0,
                    "vy": 2.0,
                    "type": "hard_bullet",
                    "color_type": "normal",
                    "dmg": 2,
                    "entered_arena": False
                })


        elif attack_type == 2:

            # Fixed warning spots that expand one at a time.
            positions = [
                (arena.left + 40, arena.top + 40),
                (arena.right - 40, arena.top + 40),
                (arena.centerx, arena.centery),
                (arena.left + 40, arena.bottom - 40),
                (arena.right - 40, arena.bottom - 40)
            ]

            for i, (x, y) in enumerate(positions):
                bullets.append({
                    "rect": pygame.Rect(x - 7, y - 7, 14, 14),
                    "cx": x,
                    "cy": y,
                    "timer": 30 + i * 20,
                    "radius": 6,
                    "max_radius": 24,
                    "type": "hard_explosion",
                    "dmg": 3
                })


        elif attack_type == 3:

            # A slow, predictable rotating ring.
            for i in range(6):
                angle = 2 * math.pi / 6 * i
                bullets.append({
                    "rect": pygame.Rect(0, 0, 10, 10),
                    "angle": angle,
                    "radius": 25,
                    "speed": 0.55,
                    "type": "hard_rotating",
                    "color_type": "normal",
                    "dmg": 1
                })


        elif attack_type == 4:

            # Slow horizontal waves, alternating direction, with no wrapping.
            for i in range(4):
                y = arena.top + 25 + i * 35
                direction = 1 if i % 2 == 0 else -1
                bullets.append({
                    "rect": pygame.Rect(
                        arena.left - 20 if direction > 0 else arena.right + 4,
                        y, 18, 12
                    ),
                    "vx": direction * 2.2,
                    "vy": 0,
                    "phase": i * 0.8,
                    "type": "hard_wave",
                    "color_type": "blue" if i % 2 == 0 else "orange",
                    "dmg": 2,
                    "entered_arena": False
                })


        elif attack_type == 5:

            # Fixed bomb positions instead of random positions.
            positions = [
                (arena.left + 45, arena.top + 45),
                (arena.right - 45, arena.top + 45),
                (arena.left + 45, arena.bottom - 45),
                (arena.right - 45, arena.bottom - 45),
                (arena.centerx, arena.centery)
            ]

            for i, (x, y) in enumerate(positions):
                bullets.append({
                    "rect": pygame.Rect(x - 6, y - 6, 12, 12),
                    "cx": x,
                    "cy": y,
                    "timer": 35 + i * 12,
                    "radius": 5,
                    "max_radius": 22,
                    "type": "hard_bomb",
                    "dmg": 3
                })


# ----------------------------------------------------
# 5. MAIN GAME LOOP
# ----------------------------------------------------

running = True

while running:

    events = pygame.event.get()

    for event in events:

        if event.type == pygame.QUIT:
            running = False

        elif (
            event.type == pygame.KEYDOWN
            and event.key == pygame.K_F11
        ):

            is_fullscreen = not is_fullscreen

            if is_fullscreen:

                screen = pygame.display.set_mode(
                    (
                        SCREEN_WIDTH,
                        SCREEN_HEIGHT
                    ),
                    pygame.FULLSCREEN
                    | pygame.SCALED
                )

            else:

                screen = pygame.display.set_mode(
                    (
                        SCREEN_WIDTH,
                        SCREEN_HEIGHT
                    ),
                    pygame.SCALED
                )


    # =================================================
    # OVERWORLD
    # =================================================

    if game_state == STATE_OVERWORLD:

        for event in events:

            if event.type == pygame.KEYDOWN:

                if in_dialogue:

                    if npc_step in (
                        "SIGN",
                        "CHEST_EMPTY"
                    ):

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            in_dialogue = False


                    elif npc_step == "CHEST_OPEN":

                        if event.key == pygame.K_x:
                            npc_step = "READ_GUIDEBOOK"

                        elif event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            in_dialogue = False


                    elif npc_step == "READ_GUIDEBOOK":

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN,
                            pygame.K_x
                        ):

                            in_dialogue = False


                    elif npc_step == "DUMMY_CHOICE":

                        if event.key in (
                            pygame.K_LEFT,
                            pygame.K_UP
                        ):

                            npc_choice = 0

                        if event.key in (
                            pygame.K_RIGHT,
                            pygame.K_DOWN
                        ):

                            npc_choice = 1

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            in_dialogue = False

                            if npc_choice == 0:

                                current_enemy = (
                                    "PRACTICE_DUMMY"
                                )

                                game_state = STATE_BATTLE
                                battle_substate = "MENU"
                                battle_text = (
                                    "You encountered Practice Dummy!"
                                )

                                menu_index = 0
                                enemy_hp = 20
                                enemy_max_hp = 20
                                enemy_mercy = 0
                                acts_done = 0


                    elif npc_step == "HELLO":

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            npc_step = "BAGEL_QUESTION"


                    elif npc_step == "BAGEL_QUESTION":

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            npc_step = "CHOICE_BAGEL"
                            npc_choice = 0


                    elif npc_step == "CHOICE_BAGEL":

                        if event.key in (
                            pygame.K_LEFT,
                            pygame.K_UP
                        ):

                            npc_choice = 0

                        if event.key in (
                            pygame.K_RIGHT,
                            pygame.K_DOWN
                        ):

                            npc_choice = 1

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            if npc_choice == 0:
                                in_dialogue = False

                            else:
                                npc_step = "PATH_AHEAD"


                    elif npc_step == "PATH_AHEAD":

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            npc_step = "ASK_ANYTHING"


                    elif npc_step == "ASK_ANYTHING":

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            npc_step = "CHOICE_ASK"
                            npc_choice = 0


                    elif npc_step == "CHOICE_ASK":

                        if event.key in (
                            pygame.K_UP,
                            pygame.K_LEFT
                        ):

                            npc_choice = (
                                npc_choice - 1
                            ) % 2

                        if event.key in (
                            pygame.K_DOWN,
                            pygame.K_RIGHT
                        ):

                            npc_choice = (
                                npc_choice + 1
                            ) % 2

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            if npc_choice == 0:
                                in_dialogue = False

                            elif npc_choice == 1:
                                npc_step = "DEFEND_1"


                    elif npc_step == "DEFEND_1":

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            npc_step = "DEFEND_2"


                    elif npc_step in (
                        "DEFEND_2",
                        "LAZY_DEV"
                    ):

                        if event.key in (
                            pygame.K_z,
                            pygame.K_RETURN
                        ):

                            in_dialogue = False


                else:

                    if event.key in (
                        pygame.K_z,
                        pygame.K_RETURN
                    ):

                        if player.colliderect(
                            talking_npc.inflate(40, 40)
                        ):

                            in_dialogue = True
                            npc_step = "HELLO"

                        elif player.colliderect(
                            sign_npc.inflate(-32, -24)
                        ):

                            in_dialogue = True
                            npc_step = "SIGN"

                        elif player.colliderect(
                            chest_npc.inflate(40, 40)
                        ):

                            in_dialogue = True

                            if not chest_opened:

                                chest_opened = True
                                npc_step = "CHEST_OPEN"

                            else:

                                npc_step = "CHEST_EMPTY"

                        elif (
                            player.colliderect(
                                dummy_npc.inflate(40, 40)
                            )
                            and not dummy_defeated
                        ):

                            in_dialogue = True
                            npc_step = "DUMMY_CHOICE"
                            npc_choice = 0


        # ------------------------------------------------
        # MOVEMENT
        # ------------------------------------------------

        is_moving = False

        if not in_dialogue:

            keys = pygame.key.get_pressed()

            dx, dy = 0, 0

            if keys[pygame.K_LEFT]:

                dx -= player_speed
                facing_right = False

            if keys[pygame.K_RIGHT]:

                dx += player_speed
                facing_right = True

            if keys[pygame.K_UP]:
                dy -= player_speed

            if keys[pygame.K_DOWN]:
                dy += player_speed

            if dx != 0 or dy != 0:
                is_moving = True

            player.x += dx

            for wall in walls:

                if player.colliderect(wall):

                    if dx > 0:
                        player.right = wall.left

                    if dx < 0:
                        player.left = wall.right

            player.y += dy

            for wall in walls:

                if player.colliderect(wall):

                    if dy > 0:
                        player.bottom = wall.top

                    if dy < 0:
                        player.top = wall.bottom

            player.x = max(
                0,
                min(
                    WORLD_WIDTH - player.width,
                    player.x
                )
            )

            player.y = max(
                0,
                min(
                    WORLD_HEIGHT - player.height,
                    player.y
                )
            )


            # Bad Sir
            if (
                not enemy_defeated
                and player.colliderect(enemy_npc)
            ):

                current_enemy = "BAD_SIR"
                game_state = STATE_BATTLE
                battle_substate = "MENU"
                battle_text = (
                    "Bad Sir Blocks The Way!"
                )

                menu_index = 0
                enemy_hp = 200
                enemy_max_hp = 200
                enemy_mercy = 0
                acts_done = 0


            # Duo
            elif (
                not all(duo_enemy_defeated)
                and player.colliderect(duo_enemy_npc)
            ):

                current_enemy = "DUO_BAD_SIRS"
                duo_enemy_types = random.sample(
                    [
                        "BAD_SIR",
                        "MID_SIR",
                        "EVIL_SIR",
                        "HARD_SIR"
                    ],
                    2
                )

                game_state = STATE_BATTLE
                battle_substate = "MENU"

                battle_text = (
                    "2 enemies got in your way! "
                    "They look synchronized."
                )

                menu_index = 0
                enemy_hp = 320
                enemy_max_hp = 320
                enemy_mercy = 0
                duo_enemy_hp = [160, 160]
                duo_enemy_mercy = [0, 0]
                duo_enemy_defeated = [False, False]
                target_index = 0
                acts_done = 0


            # Evil Sir
            elif (
                not evil_defeated
                and player.colliderect(evil_npc)
            ):

                current_enemy = "EVIL_SIR"
                game_state = STATE_BATTLE
                battle_substate = "MENU"

                battle_text = (
                    "Evil sir fills you with determination."
                )

                menu_index = 0
                enemy_hp = 200
                enemy_max_hp = 200
                enemy_mercy = 0
                acts_done = 0


            # Hard Sir
            elif (
                not hard_defeated
                and player.colliderect(hard_npc)
            ):

                current_enemy = "HARD_SIR"
                game_state = STATE_BATTLE
                battle_substate = "MENU"

                battle_text = (
                    "Hard Sir challenges you "
                    "with a suspicious amount "
                    "of preparation."
                )

                menu_index = 0
                enemy_hp = 260
                enemy_max_hp = 260
                enemy_mercy = 0
                acts_done = 0


        # ------------------------------------------------
        # PLAYER ANIMATION
        # ------------------------------------------------

        if is_moving and has_walk:

            anim_timer += 1

            if anim_timer >= ANIM_SPEED:

                anim_timer = 0

                anim_frame_idx = (
                    anim_frame_idx + 1
                ) % len(walk_frames_right)

        else:

            anim_frame_idx = 0
            anim_timer = 0


        # NPC animation

        if (
            has_talking_npc_sprite
            and len(npc_anim_frames) > 1
        ):

            npc_anim_timer += 1

            if npc_anim_timer >= NPC_ANIM_SPEED:

                npc_anim_timer = 0

                npc_anim_idx = (
                    npc_anim_idx + 1
                ) % len(npc_anim_frames)


        # ------------------------------------------------
        # CAMERA
        # ------------------------------------------------

        camera_x = max(
            0,
            min(
                WORLD_WIDTH - SCREEN_WIDTH,
                player.centerx
                - SCREEN_WIDTH // 2
            )
        )

        camera_y = max(
            0,
            min(
                WORLD_HEIGHT - SCREEN_HEIGHT,
                player.centery
                - SCREEN_HEIGHT // 2
            )
        )


        screen.fill(
            (111, 197, 255)
        )


        # ------------------------------------------------
        # WORLD BACKGROUND (SKY + CLOUDS)
        # ------------------------------------------------
        # Drawn before the grass/world. It's already sized to
        # exactly match WORLD_WIDTH x WORLD_HEIGHT, so a single
        # blit at the world origin always fully covers the camera.

        if background_sprite:

            screen.blit(
                background_sprite,
                (
                    -camera_x,
                    -camera_y
                )
            )


        # ------------------------------------------------
        # WORLD TILES
        # ------------------------------------------------

        start_col = max(
            0,
            camera_x // TILE_SIZE
        )

        end_col = min(
            GRID_COLS,
            (
                camera_x
                + SCREEN_WIDTH
            ) // TILE_SIZE
            + 1
        )

        start_row = max(
            0,
            camera_y // TILE_SIZE
        )

        end_row = min(
            GRID_ROWS,
            (
                camera_y
                + SCREEN_HEIGHT
            ) // TILE_SIZE
            + 1
        )


        for r in range(
            start_row,
            end_row
        ):

            for c in range(
                start_col,
                end_col
            ):

                tile_rect = pygame.Rect(
                    c * TILE_SIZE,
                    r * TILE_SIZE,
                    TILE_SIZE,
                    TILE_SIZE
                )

                if FLOOR_AREA.colliderect(
                    tile_rect
                ):

                    tile_idx = tile_map[r][c]

                    tile_x = (
                        c * TILE_SIZE
                        - camera_x
                    )

                    tile_y = (
                        r * TILE_SIZE
                        - camera_y
                    )

                    screen.blit(
                        grass_tiles[tile_idx],
                        (
                            tile_x,
                            tile_y
                        )
                    )


        # ------------------------------------------------
        # WALLS
        # ------------------------------------------------

        # The top wall is intentionally invisible, but its
        # collision rectangle remains in `walls`.
        # The bottom wall uses the bottom_walls texture.
        if bottom_wall_texture is not None:

            screen.blit(
                bottom_wall_texture,
                (
                    BOTTOM_WALL_RECT.x - camera_x,
                    BOTTOM_WALL_RECT.bottom - bottom_wall_texture.get_height() - camera_y
                )
            )

        else:

            # Fallback in case bottom_walls cannot be found.
            pygame.draw.rect(
                screen,
                (30, 30, 50),
                (
                    BOTTOM_WALL_RECT.x - camera_x,
                    BOTTOM_WALL_RECT.y - camera_y,
                    BOTTOM_WALL_RECT.width,
                    BOTTOM_WALL_RECT.height
                )
            )

        # Second tiled row directly underneath the bottom wall.
        if bottom_wall_bottom_texture is not None:

            screen.blit(
                bottom_wall_bottom_texture,
                (
                    BOTTOM_WALL_RECT.x - camera_x,
                    BOTTOM_WALL_RECT.bottom - camera_y
                )
            )


        # ------------------------------------------------
        # FOREST SIGN
        # ------------------------------------------------

        if has_sign_sprite:

            screen.blit(
                sign_sprite,
                (
                    sign_npc.x - camera_x,
                    sign_npc.y - camera_y
                )
            )

        else:

            pygame.draw.rect(
                screen,
                (139, 69, 19),
                (
                    sign_npc.x - camera_x,
                    sign_npc.y - camera_y,
                    sign_npc.width,
                    sign_npc.height
                )
            )

            pygame.draw.rect(
                screen,
                (90, 40, 10),
                (
                    sign_npc.x - camera_x,
                    sign_npc.y - camera_y,
                    sign_npc.width,
                    sign_npc.height
                ),
                3
            )


        # ------------------------------------------------
        # CHEST
        # ------------------------------------------------

        active_chest_sprite = (
            chest_open_sprite
            if chest_opened
            else chest_closed_sprite
        )

        if active_chest_sprite:

            screen.blit(
                active_chest_sprite,
                (
                    chest_npc.x - camera_x,
                    chest_npc.y - camera_y
                )
            )

        else:

            chest_color = (
                (255, 140, 0)
                if not chest_opened
                else (180, 90, 0)
            )

            pygame.draw.rect(
                screen,
                chest_color,
                (
                    chest_npc.x - camera_x,
                    chest_npc.y - camera_y,
                    chest_npc.width,
                    chest_npc.height
                )
            )

            pygame.draw.rect(
                screen,
                (0, 0, 0),
                (
                    chest_npc.x - camera_x,
                    chest_npc.y - camera_y,
                    chest_npc.width,
                    chest_npc.height
                ),
                3
            )


        # ------------------------------------------------
        # TALKING NPC
        # ------------------------------------------------

        if (
            has_talking_npc_sprite
            and npc_anim_frames
        ):

            npc_draw_x = (
                talking_npc.centerx
                - NPC_SPRITE_SIZE[0] // 2
                - camera_x
            )

            npc_draw_y = (
                talking_npc.bottom
                - NPC_SPRITE_SIZE[1]
                - camera_y
            )

            screen.blit(
                npc_anim_frames[npc_anim_idx],
                (
                    npc_draw_x,
                    npc_draw_y
                )
            )

        else:

            pygame.draw.rect(
                screen,
                (255, 215, 0),
                (
                    talking_npc.x - camera_x,
                    talking_npc.y - camera_y,
                    talking_npc.width,
                    talking_npc.height
                )
            )


        # ------------------------------------------------
        # BAD SIR NPC
        # ------------------------------------------------

        if not enemy_defeated:

            if has_enemy_sprite:

                screen.blit(
                    enemy_sprite_overworld,
                    (
                        enemy_npc.x - camera_x,
                        enemy_npc.y - camera_y
                    )
                )

            else:

                pygame.draw.rect(
                    screen,
                    (150, 50, 200),
                    (
                        enemy_npc.x - camera_x,
                        enemy_npc.y - camera_y,
                        enemy_npc.width,
                        enemy_npc.height
                    )
                )


        # ------------------------------------------------
        # DUO
        # ------------------------------------------------

        if not all(duo_enemy_defeated):

            if has_mid_sprite:

                screen.blit(
                    mid_sprite_overworld,
                    (
                        duo_enemy_npc.x - camera_x,
                        duo_enemy_npc.y - camera_y
                    )
                )

            elif has_enemy_sprite:

                screen.blit(
                    enemy_sprite_overworld,
                    (
                        duo_enemy_npc.x - camera_x,
                        duo_enemy_npc.y - camera_y
                    )
                )

            else:

                pygame.draw.rect(
                    screen,
                    (120, 30, 180),
                    (
                        duo_enemy_npc.x - camera_x,
                        duo_enemy_npc.y - camera_y,
                        duo_enemy_npc.width,
                        duo_enemy_npc.height
                    )
                )


        # ------------------------------------------------
        # EVIL SIR
        # ------------------------------------------------

        if not evil_defeated:

            if has_evil_sprite:

                screen.blit(
                    evil_sprite_overworld,
                    (
                        evil_npc.x - camera_x,
                        evil_npc.y - camera_y
                    )
                )

            else:

                pygame.draw.rect(
                    screen,
                    (180, 0, 0),
                    (
                        evil_npc.x - camera_x,
                        evil_npc.y - camera_y,
                        evil_npc.width,
                        evil_npc.height
                    )
                )

                pygame.draw.rect(
                    screen,
                    (40, 0, 0),
                    (
                        evil_npc.x - camera_x,
                        evil_npc.y - camera_y,
                        evil_npc.width,
                        evil_npc.height
                    ),
                    3
                )


        # ------------------------------------------------
        # HARD SIR
        # ------------------------------------------------

        if not hard_defeated:

            if has_hard_sprite:

                screen.blit(
                    hard_sprite_overworld,
                    (
                        hard_npc.x - camera_x,
                        hard_npc.y - camera_y
                    )
                )

            else:

                pygame.draw.rect(
                    screen,
                    (40, 170, 220),
                    (
                        hard_npc.x - camera_x,
                        hard_npc.y - camera_y,
                        hard_npc.width,
                        hard_npc.height
                    )
                )

                pygame.draw.rect(
                    screen,
                    (180, 240, 255),
                    (
                        hard_npc.x - camera_x,
                        hard_npc.y - camera_y,
                        hard_npc.width,
                        hard_npc.height
                    ),
                    3
                )


        # ------------------------------------------------
        # DUMMY
        # ------------------------------------------------

        if not dummy_defeated:

            dx_vis = (
                dummy_npc.x
                - camera_x
            )

            dy_vis = (
                dummy_npc.y
                - camera_y
            )

            if has_dummy_sprite:

                screen.blit(
                    dummy_sprite_overworld,
                    (
                        dx_vis - 16,
                        dy_vis - 32
                    )
                )

            else:

                pygame.draw.rect(
                    screen,
                    (139, 69, 19),
                    (
                        dx_vis + 24,
                        dy_vis + 10,
                        16,
                        54
                    )
                )

                pygame.draw.rect(
                    screen,
                    (139, 69, 19),
                    (
                        dx_vis + 8,
                        dy_vis + 25,
                        48,
                        12
                    )
                )

                pygame.draw.circle(
                    screen,
                    (220, 220, 220),
                    (
                        dx_vis + 32,
                        dy_vis + 12
                    ),
                    16
                )

                pygame.draw.circle(
                    screen,
                    (200, 50, 50),
                    (
                        dx_vis + 32,
                        dy_vis + 12
                    ),
                    10
                )


        # ------------------------------------------------
        # PLAYER
        # ------------------------------------------------

        player_draw_x = (
            player.centerx
            - PLAYER_SIZE[0] // 2
            - camera_x
        )

        player_draw_y = (
            player.bottom
            - PLAYER_SIZE[1]
            - camera_y
        )

        player_draw_pos = (
            player_draw_x,
            player_draw_y
        )


        if is_moving and has_walk:

            current_frames = (
                walk_frames_right
                if facing_right
                else walk_frames_left
            )

            screen.blit(
                current_frames[anim_frame_idx],
                player_draw_pos
            )

        elif has_idle:

            current_idle = (
                player_idle_right
                if facing_right
                else player_idle_left
            )

            screen.blit(
                current_idle,
                player_draw_pos
            )

        else:

            pygame.draw.rect(
                screen,
                (255, 50, 50),
                (
                    player.x - camera_x,
                    player.y - camera_y,
                    player.width,
                    player.height
                )
            )


        # ------------------------------------------------
        # DIALOGUE UI
        # ------------------------------------------------

        if in_dialogue:

            box_border = pygame.Rect(
                40,
                420,
                720,
                140
            )

            draw_pixel_box(
                screen,
                box_border,
                (255, 255, 255),
                (0, 0, 0),
                4
            )


            if npc_step == "SIGN":

                draw_wrapped_text(
                    screen,
                    "* Its a wooden sign. You dont know what numbers has to do with this forest.",
                    (65, 450),
                    670
                )


            elif npc_step == "CHEST_OPEN":

                draw_wrapped_text(
                    screen,
                    "* You opened the chest. Inside was a guidebook. Press X to read guidebook.",
                    (65, 450),
                    670
                )


            elif npc_step == "CHEST_EMPTY":

                draw_wrapped_text(
                    screen,
                    "* The chest is empty.",
                    (65, 450),
                    670
                )


            elif npc_step == "READ_GUIDEBOOK":

                draw_wrapped_text(
                    screen,
                    "* You open the guidebook. (Reading functionality coming soon!)",
                    (65, 450),
                    670
                )


            elif npc_step == "DUMMY_CHOICE":

                draw_wrapped_text(
                    screen,
                    "* Its a practice dummy. Do you want to use it?",
                    (65, 440),
                    670
                )

                c0 = (
                    (255, 215, 0)
                    if npc_choice == 0
                    else (255, 255, 255)
                )

                c1 = (
                    (255, 215, 0)
                    if npc_choice == 1
                    else (255, 255, 255)
                )

                screen.blit(
                    render_dialogue_text(
                        "> Yes"
                        if npc_choice == 0
                        else "  Yes",
                        c0
                    ),
                    (65, 490)
                )

                screen.blit(
                    render_dialogue_text(
                        "> No"
                        if npc_choice == 1
                        else "  No",
                        c1
                    ),
                    (250, 490)
                )


            elif npc_step == "HELLO":

                draw_wrapped_text(
                    screen,
                    "* Hello Sir!",
                    (65, 450),
                    670
                )


            elif npc_step == "BAGEL_QUESTION":

                draw_wrapped_text(
                    screen,
                    "* You here for the legendary bagel?",
                    (65, 450),
                    670
                )


            elif npc_step == "CHOICE_BAGEL":

                c0 = (
                    (255, 215, 0)
                    if npc_choice == 0
                    else (255, 255, 255)
                )

                c1 = (
                    (255, 215, 0)
                    if npc_choice == 1
                    else (255, 255, 255)
                )

                screen.blit(
                    render_dialogue_text(
                        "> Nah"
                        if npc_choice == 0
                        else "  Nah",
                        c0
                    ),
                    (65, 450)
                )

                screen.blit(
                    render_dialogue_text(
                        "> Yes"
                        if npc_choice == 1
                        else "  Yes",
                        c1
                    ),
                    (250, 450)
                )


            elif npc_step == "PATH_AHEAD":

                draw_wrapped_text(
                    screen,
                    "* Follow the path ahead. Be careful!",
                    (65, 450),
                    670
                )


            elif npc_step == "ASK_ANYTHING":

                draw_wrapped_text(
                    screen,
                    "* Anything you wanna ask?",
                    (65, 450),
                    670
                )


            elif npc_step == "CHOICE_ASK":

                opts = [
                    "No",
                    "How do i defend myself from bad sirs"
                ]

                for i, opt in enumerate(opts):

                    col = (
                        (255, 215, 0)
                        if npc_choice == i
                        else (255, 255, 255)
                    )

                    prefix = (
                        "> "
                        if npc_choice == i
                        else "  "
                    )

                    draw_wrapped_text(
                        screen,
                        prefix + opt,
                        (
                            65,
                            435 + i * 32
                        ),
                        670,
                        color=col
                    )


            elif npc_step == "DEFEND_1":

                draw_wrapped_text(
                    screen,
                    "* It would be the best to ACT enemies.",
                    (65, 450),
                    670
                )


            elif npc_step == "DEFEND_2":

                draw_wrapped_text(
                    screen,
                    "* If they are merciful enough, you can spare them!",
                    (65, 450),
                    670
                )


            elif npc_step == "LAZY_DEV":

                draw_wrapped_text(
                    screen,
                    "* Idk i guess the dev is just lazy",
                    (65, 450),
                    670
                )


            if npc_step not in (
                "CHOICE_BAGEL",
                "CHOICE_ASK",
                "DUMMY_CHOICE"
            ):

                screen.blit(
                    render_dialogue_text(
                        "[Z]",
                        (150, 150, 150),
                        font_small
                    ),
                    (710, 520)
                )


    # =================================================
    # BATTLE
    # =================================================

    elif game_state == STATE_BATTLE:

        # ------------------------------------------------
        # BATTLE INPUT
        # ------------------------------------------------

        for event in events:

            if event.type != pygame.KEYDOWN:
                continue


            # BACK / CANCEL
            # X or Shift goes back one step in the battle menus.
            if event.key in (pygame.K_x, pygame.K_LSHIFT, pygame.K_RSHIFT):

                if battle_substate == "TARGET_MENU":
                    battle_substate = "MENU"
                    target_action = "FIGHT"
                    menu_index = 0
                    continue

                if battle_substate == "ACT_MENU":
                    if current_enemy == "DUO_BAD_SIRS":
                        battle_substate = "TARGET_MENU"
                    else:
                        battle_substate = "MENU"
                    continue

                if battle_substate == "ITEM_MENU":
                    battle_substate = "MENU"
                    continue


            # MENU
            if battle_substate == "MENU":

                if event.key == pygame.K_LEFT:

                    menu_index = (
                        menu_index - 1
                    ) % 4

                if event.key == pygame.K_RIGHT:

                    menu_index = (
                        menu_index + 1
                    ) % 4


                if event.key in (
                    pygame.K_z,
                    pygame.K_RETURN
                ):

                    if menu_index == 0:

                        target_action = "FIGHT"
                        target_index = 0
                        if current_enemy == "DUO_BAD_SIRS":
                            battle_substate = "TARGET_MENU"
                        else:
                            battle_substate = "FIGHT_BAR"
                            attack_bar_pos = 0
                            fight_prep_timer = 20


                    elif menu_index == 1:

                        target_action = "ACT"
                        target_index = 0
                        if current_enemy == "DUO_BAD_SIRS":
                            battle_substate = "TARGET_MENU"
                        else:
                            battle_substate = "ACT_MENU"
                            act_index = 0


                    elif menu_index == 2:

                        if items:

                            battle_substate = "ITEM_MENU"
                            item_index = 0

                        else:

                            battle_text = (
                                "No items left!"
                            )

                            battle_substate = "TEXT"


                    elif menu_index == 3:

                        target_action = "SPARE"
                        target_index = 0
                        if current_enemy == "DUO_BAD_SIRS":
                            battle_substate = "TARGET_MENU"
                            continue

                        name_map = {
                            "PRACTICE_DUMMY": "Practice Dummy",
                            "BAD_SIR": "Bad Sir",
                            "DUO_BAD_SIRS": "Bad Sir Duo",
                            "EVIL_SIR": "Evil Sir",
                            "HARD_SIR": "Hard Sir"
                        }

                        name_str = name_map.get(
                            current_enemy,
                            "Enemy"
                        )


                        if enemy_mercy >= 100:

                            battle_text = (
                                f"You Spared {name_str}! "
                                "Earned 0 XP."
                            )

                            if current_enemy == "PRACTICE_DUMMY":
                                dummy_defeated = True

                            elif current_enemy == "BAD_SIR":
                                enemy_defeated = True

                            elif current_enemy == "DUO_BAD_SIRS":
                                duo_enemy_defeated = True

                            elif current_enemy == "EVIL_SIR":
                                evil_defeated = True

                            elif current_enemy == "HARD_SIR":
                                hard_defeated = True

                        else:

                            battle_text = (
                                f"* {name_str} is not ready "
                                "to be spared yet!"
                            )

                        battle_substate = "TEXT"


            # TARGET MENU
            elif battle_substate == "TARGET_MENU":

                living_targets = [
                    i for i in range(len(duo_enemy_types))
                    if not duo_enemy_defeated[i]
                ]

                if not living_targets:
                    battle_substate = "MENU"
                    continue

                if event.key in (pygame.K_UP, pygame.K_LEFT):
                    target_index = (target_index - 1) % len(duo_enemy_types)
                    while duo_enemy_defeated[target_index]:
                        target_index = (target_index - 1) % len(duo_enemy_types)

                if event.key in (pygame.K_DOWN, pygame.K_RIGHT):
                    target_index = (target_index + 1) % len(duo_enemy_types)
                    while duo_enemy_defeated[target_index]:
                        target_index = (target_index + 1) % len(duo_enemy_types)

                if event.key in (pygame.K_z, pygame.K_RETURN):
                    if target_action == "FIGHT":
                        battle_substate = "FIGHT_BAR"
                        attack_bar_pos = 0
                        fight_prep_timer = 20
                    elif target_action == "ACT":
                        battle_substate = "ACT_MENU"
                        act_index = 0
                    elif target_action == "SPARE":
                        target_mercy = duo_enemy_mercy[target_index]
                        target_name = {
                            "BAD_SIR": "Bad Sir",
                            "MID_SIR": "Mid Sir",
                            "EVIL_SIR": "Evil Sir",
                            "HARD_SIR": "Hard Sir"
                        }.get(duo_enemy_types[target_index], "Enemy")
                        if target_mercy >= 100:
                            duo_enemy_defeated[target_index] = True
                            battle_text = f"You Spared {target_name}! Earned 0 XP."
                        else:
                            battle_text = f"* {target_name} is not ready to be spared yet!"
                        battle_substate = "TEXT"


            # ITEM MENU
            elif battle_substate == "ITEM_MENU":

                if event.key == pygame.K_UP:

                    item_index = (
                        item_index - 1
                    ) % len(items)

                if event.key == pygame.K_DOWN:

                    item_index = (
                        item_index + 1
                    ) % len(items)


                if event.key in (
                    pygame.K_z,
                    pygame.K_RETURN
                ):

                    used_item = items.pop(
                        item_index
                    )

                    player_hp = min(
                        player_max_hp,
                        player_hp + 30
                    )

                    battle_text = (
                        "You used medkit. "
                        "Healed 30 HP."
                    )

                    battle_substate = "TEXT"


            # FIGHT BAR
            elif battle_substate == "FIGHT_BAR":

                if (
                    fight_prep_timer <= 0
                    and event.key in (
                        pygame.K_z,
                        pygame.K_RETURN
                    )
                ):

                    accuracy = abs(
                        200 - attack_bar_pos
                    )

                    damage = max(
                        10,
                        50 - accuracy // 3
                    )

                    if current_enemy == "DUO_BAD_SIRS":
                        duo_enemy_hp[target_index] -= damage
                        enemy_hp = duo_enemy_hp[target_index]
                    else:
                        enemy_hp -= damage


                    if (current_enemy == "DUO_BAD_SIRS" and duo_enemy_hp[target_index] <= 0) or (current_enemy != "DUO_BAD_SIRS" and enemy_hp <= 0):

                        enemy_hp = 0

                        xp_reward = 0
                        bucks_reward = 0


                        if current_enemy == "PRACTICE_DUMMY":

                            dummy_defeated = True


                        elif current_enemy == "BAD_SIR":

                            enemy_defeated = True


                        elif current_enemy == "DUO_BAD_SIRS":

                            duo_enemy_hp[target_index] = 0
                            duo_enemy_defeated[target_index] = True

                            if all(duo_enemy_defeated):
                                xp_reward = 8
                                bucks_reward = 10
                            else:
                                xp_reward = 0
                                bucks_reward = 0


                        elif current_enemy == "EVIL_SIR":

                            evil_defeated = True

                            xp_reward = 10
                            bucks_reward = 12


                        elif current_enemy == "HARD_SIR":

                            hard_defeated = True

                            xp_reward = 14
                            bucks_reward = 16


                        player_xp += xp_reward
                        player_bucks += bucks_reward


                        name_map = {
                            "PRACTICE_DUMMY": "Practice Dummy",
                            "BAD_SIR": "Bad Sir",
                            "DUO_BAD_SIRS": "Bad Sir Duo",
                            "EVIL_SIR": "Evil Sir",
                            "HARD_SIR": "Hard Sir"
                        }

                        if current_enemy == "DUO_BAD_SIRS":
                            defeated_name = {
                                "BAD_SIR": "Bad Sir",
                                "MID_SIR": "Mid Sir",
                                "EVIL_SIR": "Evil Sir",
                                "HARD_SIR": "Hard Sir"
                            }.get(
                                duo_enemy_types[target_index],
                                "Enemy"
                            )

                            if all(duo_enemy_defeated):
                                battle_text = (
                                    "You Took Down both enemies! "
                                    f"Earned {xp_reward} XP "
                                    f"and {bucks_reward} bucks."
                                )
                            else:
                                battle_text = (
                                    f"{defeated_name} was defeated!"
                                )
                        else:
                            name_str = name_map.get(
                                current_enemy,
                                "Enemy"
                            )

                            if (
                                xp_reward > 0
                                or bucks_reward > 0
                            ):

                                battle_text = (
                                    f"You Took Down {name_str}! "
                                    f"Earned {xp_reward} XP "
                                    f"and {bucks_reward} bucks."
                                )

                            else:

                                battle_text = (
                                    f"You Took Down {name_str}. "
                                    "Earned 0 XP."
                                )


                    else:

                        battle_text = (
                            f"Dealt {damage} DMG!"
                        )


                    battle_substate = "TEXT"


            # ACT MENU
            elif battle_substate == "ACT_MENU":

                selected_enemy_type = (
                    duo_enemy_types[target_index]
                    if current_enemy == "DUO_BAD_SIRS"
                    else current_enemy
                )

                num_act_options = (
                    2
                    if selected_enemy_type not in ("EVIL_SIR", "HARD_SIR")
                    else 3
                )

                if event.key == pygame.K_UP:
                    act_index = (act_index - 1) % num_act_options

                if event.key == pygame.K_DOWN:
                    act_index = (act_index + 1) % num_act_options

                if event.key in (pygame.K_z, pygame.K_RETURN):

                    if act_index == 0:
                        if selected_enemy_type == "PRACTICE_DUMMY":
                            battle_text = "* PRACTICE DUMMY - ATK 0 DEF 0. A target for practice."
                        elif selected_enemy_type == "BAD_SIR":
                            battle_text = "* BAD SIR - ATK 5 DEF 2"
                        elif selected_enemy_type == "MID_SIR":
                            battle_text = "* MID SIR - ATK 7 DEF 4. A tougher Bad Sir."
                        elif selected_enemy_type == "EVIL_SIR":
                            battle_text = "* EVIL SIR - ATK 12 DEF 10. Evil souls got him. RIP."
                        elif selected_enemy_type == "HARD_SIR":
                            battle_text = "* HARD SIR - ATK 7 DEF 7. Complicated attacks, but each hit is lighter."

                    elif act_index == 1:
                        if current_enemy == "DUO_BAD_SIRS":
                            duo_enemy_mercy[target_index] = min(100, duo_enemy_mercy[target_index] + 34)
                            mercy = duo_enemy_mercy[target_index]
                            if selected_enemy_type == "BAD_SIR" or selected_enemy_type == "MID_SIR":
                                battle_text = f"* You told {selected_enemy_type.replace('_', ' ').title()} a joke. ({mercy}%)"
                            elif selected_enemy_type == "EVIL_SIR":
                                battle_text = f"* You reason with Evil Sir. He weakens! ({mercy}%)"
                            else:
                                battle_text = f"* You tell Hard Sir to simplify things. ({mercy}%)"
                        elif selected_enemy_type == "PRACTICE_DUMMY":
                            enemy_mercy = 100
                            battle_text = "You told Practice Dummy that it doesnt need to fight. It got loosened."
                        elif selected_enemy_type == "BAD_SIR":
                            enemy_mercy = min(100, enemy_mercy + 34)
                            battle_text = f"* You told a joke. The Bad Sir smiled slightly. ({enemy_mercy}%)"
                        elif selected_enemy_type == "EVIL_SIR":
                            enemy_mercy = min(100, enemy_mercy + 25)
                            battle_text = ("* You reasoned with Evil Sir repeatedly. His malice breaks down!"
                                           if enemy_mercy >= 100 else f"* You try to reason with Evil Sir. He scoffs, but he weakens! ({enemy_mercy}%)")
                        elif selected_enemy_type == "HARD_SIR":
                            enemy_mercy = min(100, enemy_mercy + 20)
                            battle_text = ("* You help Hard Sir simplify his attack plans. He becomes MERCIFUL!"
                                           if enemy_mercy >= 100 else f"* You tell Hard Sir to stop overcomplicating things. ({enemy_mercy}%)")

                    elif act_index == 2 and selected_enemy_type == "EVIL_SIR":
                        battle_text = "* You tried to provoke Evil Sir. He loosened a bit."

                    battle_substate = "TEXT"


            # TEXT
            elif battle_substate == "TEXT":

                if event.key in (
                    pygame.K_z,
                    pygame.K_RETURN
                ):

                    is_def = (
                        dummy_defeated
                        if current_enemy == "PRACTICE_DUMMY"
                        else (
                            enemy_defeated
                            if current_enemy == "BAD_SIR"
                            else (
                                all(duo_enemy_defeated)
                                if current_enemy == "DUO_BAD_SIRS"
                                else (
                                    evil_defeated
                                    if current_enemy == "EVIL_SIR"
                                    else hard_defeated
                                )
                            )
                        )
                    )


                    # In a duo battle, defeating ONE enemy should NOT end the
                    # whole battle. Only leave the battle when every enemy is
                    # defeated/spared.
                    if is_def:

                        game_state = STATE_OVERWORLD

                    else:

                        battle_substate = "DODGE"

                        dodge_timer = (
                            120
                            if current_enemy == "PRACTICE_DUMMY"
                            else (
                                180
                                if current_enemy == "BAD_SIR"
                                else (
                                    220
                                    if current_enemy != "HARD_SIR"
                                    else 300
                                )
                            )
                        )

                        dodge_prep_timer = (
                            20
                            if current_enemy == "PRACTICE_DUMMY"
                            else 30
                        )


                        arena.x = ARENA_DEFAULT[0]
                        arena.y = ARENA_DEFAULT[1]
                        arena.width = ARENA_DEFAULT[2]
                        arena.height = ARENA_DEFAULT[3]


                        hard_move_x = 0
                        hard_move_y = 0
                        hard_attack_clock = 0
                        hard_rotation = 0.0
                        invincible_timer = 0


                        soul.center = arena.center


                        if current_enemy == "DUO_BAD_SIRS":
                            living_duo_count = sum(
                                1 for defeated in duo_enemy_defeated
                                if not defeated
                            )

                            # Once one of the duo is gone, the remaining
                            # enemy uses only the basic attack pattern.
                            attack_pool = (
                                [1]
                                if living_duo_count == 1
                                else [1, 2, 3]
                            )
                        else:
                            attack_pool = (
                                [1, 2, 3]
                                if current_enemy == "BAD_SIR"
                                else (
                                    [1, 2, 3, 4, 5]
                                    if current_enemy == "HARD_SIR"
                                    else [1, 2, 3, 4]
                                )
                            )


                        current_attack_type = random.choice(
                            attack_pool
                        )

                        setup_enemy_attack(
                            current_attack_type
                        )


        # ------------------------------------------------
        # FIGHT BAR UPDATE
        # ------------------------------------------------

        if battle_substate == "FIGHT_BAR":

            if fight_prep_timer > 0:

                fight_prep_timer -= 1

            else:

                attack_bar_pos += attack_bar_dir

                if (
                    attack_bar_pos <= 0
                    or attack_bar_pos >= 400
                ):

                    attack_bar_dir *= -1


        # ------------------------------------------------
        # DODGE
        # ------------------------------------------------

        if battle_substate == "DODGE":

            if current_enemy == "HARD_SIR":

                hard_attack_clock += 1


                if current_attack_type == 1:

                    hard_move_x = int(
                        math.sin(
                            hard_attack_clock
                            * 0.020
                        ) * 42
                    )

                    hard_move_y = 0


                elif current_attack_type == 3:

                    hard_move_x = 0

                    hard_move_y = int(
                        math.sin(
                            hard_attack_clock
                            * 0.018
                        ) * 28
                    )


                else:

                    hard_move_x = 0
                    hard_move_y = 0


                arena.x = (
                    ARENA_DEFAULT[0]
                    + hard_move_x
                )

                arena.y = (
                    ARENA_DEFAULT[1]
                    + hard_move_y
                )

                arena.width = ARENA_DEFAULT[2]
                arena.height = ARENA_DEFAULT[3]


            keys = pygame.key.get_pressed()

            soul_moved = False


            if keys[pygame.K_LEFT]:

                soul.x -= soul_speed
                soul_moved = True


            if keys[pygame.K_RIGHT]:

                soul.x += soul_speed
                soul_moved = True


            if keys[pygame.K_UP]:

                soul.y -= soul_speed
                soul_moved = True


            if keys[pygame.K_DOWN]:

                soul.y += soul_speed
                soul_moved = True


            soul.clamp_ip(arena)


            if invincible_timer > 0:
                invincible_timer -= 1


            if dodge_prep_timer > 0:

                dodge_prep_timer -= 1

            else:

                dodge_timer -= 1


                for b in bullets:


                    if b["type"] in (
                        "rain",
                        "aimed",
                        "bounce",
                        "ring",
                        "spiral"
                    ):

                        b["rect"].x += b["vx"]
                        b["rect"].y += b["vy"]


                        if b["type"] == "rain":

                            if (
                                b["rect"].top
                                > arena.bottom
                            ):

                                b["rect"].bottom = (
                                    arena.top
                                )


                        elif b["type"] == "bounce":

                            if arena.colliderect(b["rect"]):
                                b["entered_arena"] = True

                            if b.get("entered_arena"):

                                if (
                                    b["rect"].left
                                    <= arena.left
                                    or b["rect"].right
                                    >= arena.right
                                ):

                                    b["vx"] *= -1


                                if (
                                    b["rect"].top
                                    <= arena.top
                                    or b["rect"].bottom
                                    >= arena.bottom
                                ):

                                    b["vy"] *= -1


                        elif b["type"] in (
                            "aimed",
                            "ring",
                            "spiral"
                        ):

                            # These fly a straight line instead of
                            # bouncing. Once one has actually been
                            # inside the box and then fully leaves
                            # again, retire it instead of letting it
                            # keep flying off past the box forever.
                            if arena.colliderect(b["rect"]):

                                b["entered_arena"] = True

                            elif b.get("entered_arena"):

                                b["expired"] = True


                    elif b["type"] == "hard_bullet":

                        b["rect"].x += b["vx"]
                        b["rect"].y += b["vy"]

                        # Hard Sir bullets simply disappear after leaving the box.
                        if arena.colliderect(b["rect"]):
                            b["entered_arena"] = True
                        elif b.get("entered_arena"):
                            b["expired"] = True


                    elif b["type"] == "hard_rotating":

                        hard_rotation += 0.004

                        b["radius"] += b["speed"]

                        angle = (
                            b["angle"]
                            + hard_rotation
                        )

                        b["rect"].center = (
                            int(
                                arena.centerx
                                + math.cos(angle)
                                * b["radius"]
                            ),
                            int(
                                arena.centery
                                + math.sin(angle)
                                * b["radius"]
                            )
                        )


                        # Let the rotating projectile travel all the way to
                        # the nearest edge in its current direction.  Unlike
                        # a circular orbit, this reaches the corners too.
                        half_w = arena.width / 2 - b["rect"].width / 2 - 2
                        half_h = arena.height / 2 - b["rect"].height / 2 - 2

                        cos_a = math.cos(angle)
                        sin_a = math.sin(angle)

                        distances = []

                        if abs(cos_a) > 0.0001:
                            distances.append(half_w / abs(cos_a))

                        if abs(sin_a) > 0.0001:
                            distances.append(half_h / abs(sin_a))

                        max_orbit_radius = min(distances)

                        if b["radius"] >= max_orbit_radius:
                            b["radius"] = 12

                        b["rect"].center = (
                            int(
                                arena.centerx
                                + cos_a * b["radius"]
                            ),
                            int(
                                arena.centery
                                + sin_a * b["radius"]
                            )
                        )


                    elif b["type"] in (
                        "hard_explosion",
                        "hard_bomb"
                    ):

                        if b["timer"] > 0:

                            b["timer"] -= 1

                        else:

                            b["radius"] += 2.5

                            if (
                                b["radius"]
                                > b["max_radius"]
                            ):

                                b["radius"] = 0

                                b["timer"] = random.randint(
                                    25,
                                    55
                                )

                                b["cx"] = random.randint(
                                    arena.left + 15,
                                    arena.right - 15
                                )

                                b["cy"] = random.randint(
                                    arena.top + 15,
                                    arena.bottom - 15
                                )


                            b["rect"].center = (
                                int(b["cx"]),
                                int(b["cy"])
                            )

                            b["rect"].size = (
                                int(
                                    max(
                                        1,
                                        b["radius"] * 2
                                    )
                                ),
                                int(
                                    max(
                                        1,
                                        b["radius"] * 2
                                    )
                                )
                            )


                    elif b["type"] == "hard_wave":

                        b["rect"].x += b["vx"]

                        b["rect"].y = int(
                            b["rect"].y
                            + math.sin(
                                pygame.time.get_ticks()
                                / 140
                                + b["phase"]
                            ) * 2
                        )


                        if not arena.colliderect(b["rect"]):
                            b["expired"] = True


                    elif b["type"] == "hard_anchor":

                        b["rect"].center = (
                            arena.center
                        )


                    elif b["type"] == "color_wave":

                        b["rect"].x += b["vx"]


                        if (
                            b["vx"] > 0
                            and b["rect"].left
                            > arena.right + 20
                        ):

                            b["rect"].right = (
                                arena.left - 10
                            )


                        elif (
                            b["vx"] < 0
                            and b["rect"].right
                            < arena.left - 20
                        ):

                            b["rect"].left = (
                                arena.right + 10
                            )


                    elif b["type"] == "laser":

                        if b["timer"] > 0:

                            b["timer"] -= 1

                        elif b["active"] > 0:

                            b["active"] -= 1


                    if b.get("expired"):
                        continue


                    # ------------------------------------------------
                    # COLLISION
                    # ------------------------------------------------

                    if invincible_timer == 0:

                        is_hit = False

                        dmg = b.get(
                            "dmg",
                            1
                        )


                        if b["type"] == "laser":

                            if (
                                b["timer"] <= 0
                                and b["active"] > 0
                                and soul.colliderect(
                                    b["rect"]
                                )
                            ):

                                is_hit = True


                        elif b["type"] in (
                            "hard_explosion",
                            "hard_bomb"
                        ):

                            if (
                                b["timer"] <= 0
                                and b.get(
                                    "radius",
                                    0
                                ) > 4
                            ):

                                dist = math.hypot(
                                    soul.centerx
                                    - b["cx"],
                                    soul.centery
                                    - b["cy"]
                                )

                                if dist <= (
                                    b["radius"]
                                    + max(
                                        soul.width,
                                        soul.height
                                    ) / 2
                                ):

                                    is_hit = True


                        elif b["type"] == "hard_anchor":

                            is_hit = False


                        else:

                            if soul.colliderect(
                                b["rect"]
                            ):

                                col_type = b.get(
                                    "color_type",
                                    "normal"
                                )


                                if col_type == "normal":

                                    is_hit = True


                                elif (
                                    col_type == "blue"
                                    and soul_moved
                                ):

                                    is_hit = True


                                elif (
                                    col_type == "orange"
                                    and not soul_moved
                                ):

                                    is_hit = True


                        if is_hit:

                            player_hp = max(
                                0,
                                player_hp - dmg
                            )

                            invincible_timer = 25


                            if player_hp <= 0:

                                game_state = STATE_DEATH
                                death_alpha = 0


                bullets = [
                    b for b in bullets
                    if not b.get("expired")
                ]


                if dodge_timer <= 0:

                    battle_substate = "MENU"

                    arena.x = ARENA_DEFAULT[0]
                    arena.y = ARENA_DEFAULT[1]
                    arena.width = ARENA_DEFAULT[2]
                    arena.height = ARENA_DEFAULT[3]

                    battle_text = random.choice(
                        RANDOM_FLAVOR_TEXTS[
                            current_enemy
                        ]
                    )


        # ------------------------------------------------
        # BATTLE RENDER
        # ------------------------------------------------

        screen.fill(
            (0, 0, 0)
        )


        is_def = (
            dummy_defeated
            if current_enemy == "PRACTICE_DUMMY"
            else (
                enemy_defeated
                if current_enemy == "BAD_SIR"
                else (
                    all(duo_enemy_defeated)
                    if current_enemy == "DUO_BAD_SIRS"
                    else (
                        evil_defeated
                        if current_enemy == "EVIL_SIR"
                        else hard_defeated
                    )
                )
            )
        )


        if not is_def:

            if current_enemy == "BAD_SIR":

                choppy_time_step = (
                    pygame.time.get_ticks()
                    // 150
                )

                enemy_sway_x = int(
                    math.sin(
                        choppy_time_step * 0.5
                    ) * 24
                )


                if has_enemy_sprite:

                    screen.blit(
                        enemy_sprite_battle,
                        (
                            336 + enemy_sway_x,
                            45
                        )
                    )

                else:

                    pygame.draw.rect(
                        screen,
                        (150, 50, 200),
                        (
                            360 + enemy_sway_x,
                            65,
                            80,
                            80
                        )
                    )


            elif current_enemy == "DUO_BAD_SIRS":

                choppy_time_step = (
                    pygame.time.get_ticks()
                    // 150
                )

                enemy_sway_y = int(
                    math.sin(
                        choppy_time_step * 0.5
                    ) * 12
                )

                # Draw the two randomly selected enemies.
                duo_sprite_data = {
                    "BAD_SIR": (
                        enemy_sprite_battle,
                        has_enemy_sprite,
                        (150, 50, 200)
                    ),
                    "MID_SIR": (
                        mid_sprite_battle,
                        has_mid_sprite,
                        (120, 30, 180)
                    ),
                    "EVIL_SIR": (
                        evil_sprite_battle,
                        has_evil_sprite,
                        (180, 0, 0)
                    ),
                    "HARD_SIR": (
                        hard_sprite_battle,
                        has_hard_sprite,
                        (40, 170, 220)
                    )
                }

                duo_positions = [
                    (260, 45 + enemy_sway_y),
                    (410, 45 - enemy_sway_y)
                ]

                for duo_i, (duo_type, duo_pos) in enumerate(zip(
                    duo_enemy_types,
                    duo_positions
                )):

                    if duo_enemy_defeated[duo_i]:
                        continue

                    duo_sprite, duo_has_sprite, duo_fallback_color = (
                        duo_sprite_data[duo_type]
                    )

                    if duo_has_sprite:

                        screen.blit(
                            duo_sprite,
                            duo_pos
                        )

                    else:

                        pygame.draw.rect(
                            screen,
                            duo_fallback_color,
                            (
                                duo_pos[0] + 20,
                                duo_pos[1] + 20,
                                80,
                                80
                            )
                        )

            elif current_enemy == "EVIL_SIR":

                choppy_time_step = (
                    pygame.time.get_ticks()
                    // 100
                )

                enemy_sway_x = int(
                    math.sin(
                        choppy_time_step * 0.8
                    ) * 16
                )

                enemy_sway_y = int(
                    math.cos(
                        choppy_time_step * 0.8
                    ) * 8
                )


                if has_evil_sprite:

                    screen.blit(
                        evil_sprite_battle,
                        (
                            330 + enemy_sway_x,
                            35 + enemy_sway_y
                        )
                    )

                else:

                    ebx = 350 + enemy_sway_x
                    eby = 50 + enemy_sway_y

                    pygame.draw.rect(
                        screen,
                        (180, 0, 0),
                        (
                            ebx,
                            eby,
                            100,
                            100
                        )
                    )

                    pygame.draw.rect(
                        screen,
                        (40, 0, 0),
                        (
                            ebx,
                            eby,
                            100,
                            100
                        ),
                        5
                    )

                    pygame.draw.rect(
                        screen,
                        (255, 255, 0),
                        (
                            ebx + 20,
                            eby + 30,
                            20,
                            10
                        )
                    )

                    pygame.draw.rect(
                        screen,
                        (255, 255, 0),
                        (
                            ebx + 60,
                            eby + 30,
                            20,
                            10
                        )
                    )


            elif current_enemy == "HARD_SIR":

                choppy_time_step = (
                    pygame.time.get_ticks()
                    // 90
                )

                enemy_sway_x = int(
                    math.sin(
                        choppy_time_step * 0.7
                    ) * 12
                )

                enemy_sway_y = int(
                    math.cos(
                        choppy_time_step * 0.9
                    ) * 7
                )


                if has_hard_sprite:

                    screen.blit(
                        hard_sprite_battle,
                        (
                            325 + enemy_sway_x,
                            25 + enemy_sway_y
                        )
                    )

                else:

                    pygame.draw.rect(
                        screen,
                        (40, 170, 220),
                        (
                            350 + enemy_sway_x,
                            55 + enemy_sway_y,
                            100,
                            110
                        )
                    )

                    pygame.draw.rect(
                        screen,
                        (180, 240, 255),
                        (
                            350 + enemy_sway_x,
                            55 + enemy_sway_y,
                            100,
                            110
                        ),
                        5
                    )


            else:

                if has_dummy_sprite:

                    screen.blit(
                        dummy_sprite_battle,
                        (
                            304,
                            15
                        )
                    )

                else:

                    pygame.draw.rect(
                        screen,
                        (139, 69, 19),
                        (
                            388,
                            80,
                            24,
                            100
                        )
                    )

                    pygame.draw.rect(
                        screen,
                        (139, 69, 19),
                        (
                            340,
                            110,
                            120,
                            16
                        )
                    )

                    pygame.draw.circle(
                        screen,
                        (220, 220, 220),
                        (
                            400,
                            65
                        ),
                        30
                    )

                    pygame.draw.circle(
                        screen,
                        (200, 50, 50),
                        (
                            400,
                            65
                        ),
                        18
                    )

                    pygame.draw.circle(
                        screen,
                        (220, 220, 220),
                        (
                            400,
                            65
                        ),
                        8
                    )


        # ------------------------------------------------
        # DODGE RENDER
        # ------------------------------------------------

        if battle_substate == "DODGE":

            draw_pixel_box(
                screen,
                arena,
                (255, 255, 255),
                (0, 0, 0),
                5
            )


            if invincible_timer % 4 < 2:

                if soul_sprite:

                    screen.blit(
                        soul_sprite,
                        (
                            soul.centerx
                            - soul_sprite.get_width()
                            // 2,

                            soul.centery
                            - soul_sprite.get_height()
                            // 2
                        )
                    )

                else:

                    pygame.draw.rect(
                        screen,
                        (0, 255, 120),
                        soul
                    )


            # ------------------------------------------------
            # BULLETS
            # ------------------------------------------------

            for b in bullets:

                if b["type"] in (
                    "hard_explosion",
                    "hard_bomb"
                ):

                    if b["timer"] > 0:

                        warn = (
                            12
                            + int(
                                5
                                * math.sin(
                                    pygame.time.get_ticks()
                                    / 70
                                )
                            )
                        )

                        pygame.draw.rect(
                            screen,
                            (255, 80, 80),
                            b["rect"],
                            2
                        )

                        pygame.draw.rect(
                            screen,
                            (255, 180, 0),
                            b["rect"],
                            1
                        )

                    elif b.get(
                        "radius",
                        0
                    ) > 0:

                        center = (
                            int(b["cx"]),
                            int(b["cy"])
                        )

                        pygame.draw.circle(
                            screen,
                            (255, 120, 20),
                            center,
                            int(b["radius"]),
                            3
                        )

                        if b["radius"] > 12:

                            pygame.draw.circle(
                                screen,
                                (255, 240, 100),
                                center,
                                int(
                                    b["radius"]
                                    // 2
                                ),
                                2
                            )


                elif b["type"] == "hard_anchor":

                    pygame.draw.rect(
                        screen,
                        (180, 240, 255),
                        b["rect"],
                        1
                    )


                elif b["type"] == "laser":

                    if b["timer"] > 0:

                        warn_surf = pygame.Surface(
                            (
                                b["rect"].width,
                                b["rect"].height
                            ),
                            pygame.SRCALPHA
                        )

                        warn_color = (
                            255,
                            50,
                            50,
                            90
                            if (
                                pygame.time.get_ticks()
                                // 80
                            ) % 2 == 0
                            else 190
                        )

                        warn_surf.fill(
                            warn_color
                        )

                        screen.blit(
                            warn_surf,
                            b["rect"].topleft
                        )

                    elif b["active"] > 0:

                        pygame.draw.rect(
                            screen,
                            (255, 255, 200),
                            b["rect"]
                        )

                        pygame.draw.rect(
                            screen,
                            (255, 30, 30),
                            b["rect"],
                            4
                        )


                else:

                    col_type = b.get(
                        "color_type",
                        "normal"
                    )


                    if col_type == "blue":

                        bullet_color = (
                            0,
                            220,
                            255
                        )

                    elif col_type == "orange":

                        bullet_color = (
                            255,
                            140,
                            0
                        )

                    else:

                        bullet_color = (
                            255,
                            255,
                            255
                        )


                    pygame.draw.rect(
                        screen,
                        bullet_color,
                        b["rect"]
                    )


        # ------------------------------------------------
        # TARGET MENU
        # ------------------------------------------------

        elif battle_substate == "TARGET_MENU":

            # Enemy target selection uses the same battle box as the other
            # menus, so it does not cover the enemy sprites at the top.
            # The targets are stacked vertically and each one shows its HP.
            box_rect = pygame.Rect(80, 200, 640, 170)
            draw_pixel_box(screen, box_rect, (255, 255, 255), (0, 0, 0), 5)

            target_names = {
                "BAD_SIR": "Bad Sir",
                "MID_SIR": "Mid Sir",
                "EVIL_SIR": "Evil Sir",
                "HARD_SIR": "Hard Sir"
            }

            for i, enemy_type in enumerate(duo_enemy_types):
                name = target_names.get(enemy_type, "Enemy")
                text_y = 225 + i * 55

                if duo_enemy_defeated[i]:
                    if target_action in ("ACT", "SPARE"):
                        label = f"{name}   MERCY 100%   DEFEATED"
                    else:
                        label = f"{name}   HP 0/160   DEFEATED"
                    col = (100, 100, 100)
                else:
                    col = (255, 215, 0) if target_index == i else (255, 255, 255)
                    if target_action == "ACT" or target_action == "SPARE":
                        mercy_now = max(0, min(100, duo_enemy_mercy[i]))
                        label = f"{name}   MERCY {mercy_now}%"
                    else:
                        hp_now = max(0, duo_enemy_hp[i])
                        label = f"{name}   HP {hp_now}/160"

                text_surface = render_pixel(label, col)

                # Put a small selection arrow to the left of the selected
                # enemy, rather than changing the layout of the text.
                if target_index == i and not duo_enemy_defeated[i]:
                    arrow = render_pixel(">", col)
                    screen.blit(arrow, (105, text_y))

                screen.blit(
                    text_surface,
                    (145, text_y)
                )


        # ------------------------------------------------
        # FIGHT BAR
        # ------------------------------------------------

        elif battle_substate == "FIGHT_BAR":

            box_rect = pygame.Rect(
                80,
                200,
                640,
                170
            )

            draw_pixel_box(
                screen,
                box_rect,
                (255, 255, 255),
                (0, 0, 0),
                5
            )


            bar_track = pygame.Rect(
                120,
                260,
                560,
                50
            )

            # Custom fight-bar texture.  It replaces the old plain track/green hit area.
            if fight_bar_texture is not None:
                bar_scaled = pygame.transform.scale(
                    fight_bar_texture,
                    (bar_track.width, bar_track.height)
                )
                screen.blit(bar_scaled, bar_track)
            else:
                pygame.draw.rect(
                    screen,
                    (20, 20, 20),
                    bar_track
                )

                pygame.draw.rect(
                    screen,
                    (0, 255, 100),
                    (
                        380,
                        260,
                        40,
                        50
                    )
                )


            cursor_x = (
                120
                + (
                    attack_bar_pos
                    * 560
                    // 400
                )
            )

            if fight_landing_texture is not None:
                landing_height = 70
                ratio = (
                    fight_landing_texture.get_width()
                    / fight_landing_texture.get_height()
                )
                landing_width = max(1, int(landing_height * ratio))
                landing_scaled = pygame.transform.scale(
                    fight_landing_texture,
                    (landing_width, landing_height)
                )
                landing_rect = landing_scaled.get_rect(
                    center=(cursor_x, 285)
                )
                screen.blit(landing_scaled, landing_rect)
            else:
                pygame.draw.rect(
                    screen,
                    (255, 50, 50),
                    (
                        cursor_x - 6,
                        250,
                        12,
                        70
                    )
                )


        # ------------------------------------------------
        # ACT MENU
        # ------------------------------------------------

        elif battle_substate == "ACT_MENU":

            box_rect = pygame.Rect(
                80,
                200,
                640,
                170
            )

            draw_pixel_box(
                screen,
                box_rect,
                (255, 255, 255),
                (0, 0, 0),
                5
            )


            if current_enemy in (
                "EVIL_SIR",
                "HARD_SIR"
            ):

                opts = [
                    "* Check",
                    "* Reason",
                    "* Provoke"
                ]

                for i, opt in enumerate(opts):

                    col = (
                        (255, 215, 0)
                        if act_index == i
                        else (255, 255, 255)
                    )

                    screen.blit(
                        render_pixel(
                            opt,
                            col
                        ),
                        (
                            120,
                            225 + i * 35
                        )
                    )

            else:

                c1 = (
                    (255, 215, 0)
                    if act_index == 0
                    else (255, 255, 255)
                )

                c2 = (
                    (255, 215, 0)
                    if act_index == 1
                    else (255, 255, 255)
                )


                screen.blit(
                    render_pixel(
                        "* Check",
                        c1
                    ),
                    (120, 230)
                )


                act_2_label = (
                    "* Talk"
                    if current_enemy
                    == "PRACTICE_DUMMY"
                    else "* Tell Joke"
                )


                screen.blit(
                    render_pixel(
                        act_2_label,
                        c2
                    ),
                    (120, 270)
                )


        # ------------------------------------------------
        # ITEM MENU
        # ------------------------------------------------

        elif battle_substate == "ITEM_MENU":

            box_rect = pygame.Rect(
                80,
                200,
                640,
                170
            )

            draw_pixel_box(
                screen,
                box_rect,
                (255, 255, 255),
                (0, 0, 0),
                5
            )


            for idx, itm in enumerate(items):

                col = (
                    (255, 215, 0)
                    if idx == item_index
                    else (255, 255, 255)
                )

                screen.blit(
                    render_pixel(
                        f"* {itm}",
                        col
                    ),
                    (
                        120,
                        230 + idx * 40
                    )
                )


        # ------------------------------------------------
        # TEXT
        # ------------------------------------------------

        else:

            box_rect = pygame.Rect(
                80,
                200,
                640,
                170
            )

            draw_pixel_box(
                screen,
                box_rect,
                (255, 255, 255),
                (0, 0, 0),
                5
            )

            draw_wrapped_text(
                screen,
                battle_text,
                (110, 230),
                580
            )


        # ------------------------------------------------
        # PLAYER HEALTH
        # ------------------------------------------------

        hud_y = 395

        screen.blit(
            render_pixel(
                f"YOU  LV 1  XP:{player_xp}",
                (255, 255, 255),
                font_small
            ),
            (
                80,
                hud_y
            )
        )

        screen.blit(
            render_pixel(
                "HP",
                (255, 255, 255),
                font_small
            ),
            (
                270,
                hud_y
            )
        )


        max_bar_w = 120

        cur_bar_w = int(
            max_bar_w
            * (
                player_hp
                / player_max_hp
            )
        )


        pygame.draw.rect(
            screen,
            (180, 0, 0),
            (
                295,
                hud_y + 2,
                max_bar_w,
                18
            )
        )

        pygame.draw.rect(
            screen,
            (255, 255, 0),
            (
                295,
                hud_y + 2,
                cur_bar_w,
                18
            )
        )


        screen.blit(
            render_pixel(
                f"{player_hp} / {player_max_hp}",
                (255, 255, 255),
                font_small
            ),
            (
                430,
                hud_y
            )
        )


        screen.blit(
            render_pixel(
                f"${player_bucks} BUCKS",
                (255, 215, 0),
                font_small
            ),
            (
                550,
                hud_y
            )
        )


        # ------------------------------------------------
        # ACTION BUTTONS
        # ------------------------------------------------

        options = [
            "FIGHT",
            "ACT",
            "ITEM",
            "SPARE"
        ]

        button_w = 135
        button_h = 42

        start_x = 80
        spacing = 168


        for i, opt in enumerate(options):

            bx = start_x + i * spacing
            by = 440

            btn_rect = pygame.Rect(
                bx,
                by,
                button_w,
                button_h
            )

            is_selected = (
                i == menu_index
                and battle_substate == "MENU"
            )

            # The keyboard-selected FIGHT button uses the hovered texture.
            if opt == "FIGHT" and fight_button_texture is not None:
                texture = (
                    fight_button_hovered_texture
                    if is_selected and fight_button_hovered_texture is not None
                    else fight_button_texture
                )

                if draw_item_button_texture(
                    screen,
                    texture,
                    btn_rect.center,
                    72
                ):
                    continue

            # The keyboard-selected ITEM button uses the hovered texture.
            if opt == "ITEM" and item_button_texture is not None:
                texture = (
                    item_button_hovered_texture
                    if is_selected and item_button_hovered_texture is not None
                    else item_button_texture
                )

                if draw_item_button_texture(
                    screen,
                    texture,
                    btn_rect.center,
                    72
                ):
                    continue

            # The keyboard-selected ACT button uses the hovered texture.
            if opt == "ACT" and act_button_texture is not None:
                texture = (
                    act_button_hovered_texture
                    if is_selected and act_button_hovered_texture is not None
                    else act_button_texture
                )

                if draw_item_button_texture(
                    screen,
                    texture,
                    btn_rect.center,
                    72
                ):
                    continue

            # SPARE has four textures:
            # normal / hovered, plus ready-to-spare / hovered-ready.
            if opt == "SPARE" and spare_button_texture is not None:
                if current_enemy == "DUO_BAD_SIRS":
                    spare_ready = any(
                        not duo_enemy_defeated[i]
                        and duo_enemy_mercy[i] >= 100
                        for i in range(len(duo_enemy_types))
                    )
                else:
                    spare_ready = enemy_mercy >= 100

                if spare_ready:
                    texture = (
                        ready_spare_button_hovered_texture
                        if is_selected and ready_spare_button_hovered_texture is not None
                        else ready_spare_button_texture
                    )
                else:
                    texture = (
                        spare_button_hovered_texture
                        if is_selected and spare_button_hovered_texture is not None
                        else spare_button_texture
                    )

                if draw_item_button_texture(
                    screen,
                    texture,
                    btn_rect.center,
                    72
                ):
                    continue

            border_color = (
                (255, 165, 0)
                if is_selected
                else (180, 100, 0)
            )

            text_color = (
                (255, 215, 0)
                if is_selected
                else (255, 165, 0)
            )

            if opt == "SPARE" and enemy_mercy >= 100:
                text_color = (255, 255, 0)

            fill_bg = (
                (30, 15, 0)
                if is_selected
                else (0, 0, 0)
            )

            draw_pixel_box(
                screen,
                btn_rect,
                border_color,
                fill_bg,
                3
            )

            txt_surf = render_pixel(
                opt,
                text_color,
                font
            )

            tx = bx + (button_w - txt_surf.get_width()) // 2
            ty = by + (button_h - txt_surf.get_height()) // 2

            screen.blit(
                txt_surf,
                (tx, ty)
            )


    # =================================================
    # DEATH
    # =================================================

    elif game_state == STATE_DEATH:

        death_alpha += 4

        if death_alpha > 255:
            death_alpha = 255


        fade_overlay = pygame.Surface(
            (
                SCREEN_WIDTH,
                SCREEN_HEIGHT
            )
        )

        fade_overlay.fill(
            (255, 255, 255)
        )

        fade_overlay.set_alpha(
            death_alpha
        )

        screen.blit(
            fade_overlay,
            (0, 0)
        )


        if death_alpha >= 255:

            player.x = 400
            player.y = 300

            player_hp = player_max_hp

            game_state = STATE_OVERWORLD

            death_alpha = 0


    pygame.display.flip()

    clock.tick(60)


pygame.quit()
sys.exit()