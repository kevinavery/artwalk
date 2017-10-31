
from __future__ import print_function
from colorthief import ColorThief
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000
from colormath.color_objects import LabColor, sRGBColor
from imagepreview import ImagePreview
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
import math
import random
import threading


def hex_to_rgb(hex):
  return tuple([int(hex[i:i + 2], 16) for i in range(1, 6, 2)])


def rgb_to_hex(rgb):
  return '#' + ''.join(['0{0:x}'.format(v) if v < 16
    else '{0:x}'.format(v) for v in rgb])


def linear_gradient(start, finish, n):
  gradient = [start]

  for t in xrange(1, n):
    # Note: There are other ways to blend colors:
    # https://stackoverflow.com/questions/22607043/color-gradient-algorithm
    # https://bsou.io/posts/color-gradients-with-python
    color_vec = [
      int(start[j] + (float(t) / (n - 1)) * (finish[j] - start[j]))
      for j in range(3)
    ]
    gradient.append(tuple(color_vec))

  return gradient


def draw_dot(x, y, r, color, img):
  draw = ImageDraw.Draw(img)
  draw.ellipse((x - r, y - r, x + r, y + r), color)


def clamp(x, a, b):
  if x < a:
    return a
  elif x > b:
    return b
  else:
    return x


def safe_get_pixel(x, y, img):
  x = clamp(x, 0, img.width - 1)
  y = clamp(y, 0, img.height - 1)
  return img.getpixel((x, y))


def draw_section(ox, oy, o, k, palette):
  # Draw a gradient as the background
  sample_x = ox + (k.width / 2)
  sample_y1 = oy
  sample_y2 = oy + k.height - 1
  color_start = safe_get_pixel(sample_x, sample_y1, o)
  color_finish = safe_get_pixel(sample_x, sample_y2, o)
  if palette:
    color_start, color_finish = select_colors(color_start, color_finish, palette)
  gradient = linear_gradient(color_start, color_finish, k.height)

  for y in xrange(0, k.height):
    for x in xrange(0, k.width):
      c = gradient[y]
      k.putpixel((x, y), c)

  # Draw dots to create image detail
  dot_radius_factor = 34
  dot_radius = k.width / dot_radius_factor
  num_dots = 1000
  for _ in xrange(num_dots):
    x = random.randint(0, k.width - 1)
    y = random.randint(0, k.height - 1)

    # The further we are from the center of the current region,
    # the further we sample outside the current region
    dx = (x - k.width) / 2
    dy = (y - k.height) / 2
    color = safe_get_pixel(ox + x + dx, oy + y + dy, o)
    if palette:
      color = nearest_color(color, palette)
    draw_dot(x, y, dot_radius, color, k)


def adjust(img, color=1.0, contrast=1.0, brightness=1.0):
  colorer = ImageEnhance.Color(img)
  img = colorer.enhance(color)

  contraster = ImageEnhance.Contrast(img)
  img = contraster.enhance(contrast)

  brightener = ImageEnhance.Brightness(img)
  img = brightener.enhance(brightness)

  return img


def get_mmcq_palette(filepath, colorCount, quality):
  # This clusters similar colors found in the input image
  # using the MMCQ (modified median cut quantization) algo.
  color_thief = ColorThief(filepath)
  return color_thief.get_palette(color_count=colorCount, quality=quality)


def get_material_palette():
  palette = []
  with open('material_color_palette.txt') as f:
    lines = f.readlines()
    for line in lines:
      line = line.strip()
      if line.startswith('#'):
        palette.append(hex_to_rgb(line))
  return palette


def rgb_to_lab(rgb):
  rgb = sRGBColor(rgb[0], rgb[1], rgb[2], is_upscaled=True)
  return convert_color(rgb, LabColor)


def diff_rgb(c0, c1):
  return math.sqrt((c1[0] - c0[0])**2 + (c1[1] - c0[1])**2 + (c1[2] - c0[2])**2)


def diff_rgb_lab(rgb, lab):
  return delta_e_cie2000(rgb_to_lab(rgb), lab)


def nearest_color(c, palette):
  return min(palette, key=lambda cp: diff_rgb(c, cp))
  #return min(palette, key=lambda cp: diff_rgb_lab(c, cp['lab']))['rgb']


def select_colors(c0, c1, palette):
  # Return two colors r0, r1 in palette closest to c0 and c1
  r0 = nearest_color(c0, palette)

  #remaining_palette = list(palette)
  #remaining_palette.remove(r0)
  remaining_palette = palette
  r1 = nearest_color(c1, remaining_palette)

  return (r0, r1)


def build_mask(w, h):
  mask = Image.new('RGBA', (w, h))

  draw = ImageDraw.Draw(mask)
  draw.rectangle([(0, 0), (w - 1, h - 1)], fill=(0, 0, 0, 0))

  points = [(w / 3, 0), (w, h * 2 / 3), (w * 2 / 3, h), (0, h / 3)]
  draw.polygon(points, fill=(255, 255, 255, 255))

  return mask


def gen_sections(x, y, sw, sh, w, h):
  # Computes a single row of parallelograms going from lower left
  # to upper right, which should overflow off the edges to fully
  # cover the image.
  #
  # (x, y) is the top-left point to start from
  # (sw, sh) is the size of the section
  # (w, h) is the size of the overall image to cover
  #
  # Returns the list of top-left points for each parallelogram box
  sections = []
  while (x < w) and (y + sh >= 0):
    if (x + sw >= 0) and (y < h):
      sections.append((x, y))

    x += sw / 3
    y -= sh / 3

  return sections


def show_palette(palette):
  w_color = 100
  h_color = 40
  palette_image = Image.new('RGB', (w_color, h_color * len(palette)))
  for i in xrange(len(palette)):
    draw = ImageDraw.Draw(palette_image)
    top_left = (0, i * h_color)
    bottom_right = (w_color - 1, ((i + 1) * h_color) - 1)
    draw.rectangle([top_left, bottom_right], fill=palette[i])
  palette_image.show()


def render(filepath, o, preview):
  w_section = o.width / 8
  h_section = w_section * 2 / 3

  print(w_section, h_section)

  r = Image.new(o.mode, o.size)
  mask = build_mask(w_section, h_section)

  # Note: I tried using custom palettes to control the output
  # colors but the results were not as good.
  #palette = get_mmcq_palette(filepath, 256, 1)
  #palette = get_material_palette()
  palette = None
  #show_palette(palette)
  #palette = [{'rgb': c, 'lab': rgb_to_lab(c)} for c in palette]

  x_init = int(-w_section * (1 + random.random()))
  y_init = int(-h_section * (1 + random.random()))
  sections = gen_sections(x_init, y_init, w_section, h_section, o.width, o.height)
  row = 0

  while y_init < 0 or len(sections) > 0:
    print('row={} sections={}'.format(row, sections))

    for (x, y) in sections:
      # Draw the current section, then paste it on the output with the shape mask.
      k = Image.new(o.mode, (w_section, h_section))
      draw_section(x, y, o, k, palette)
      r.paste(k, box=(x, y), mask=mask)

      preview.receive(r)

    y_init += (h_section * 4 / 3) - 1
    sections = gen_sections(x_init, y_init, w_section, h_section, o.width, o.height)
    row += 1

  r.save('output/out.jpg')
  r.show()

  preview.receive(ImagePreview.CLOSE_COMMAND)


def main():
  filepath = 'input/IMG_2053.JPG'
  o = Image.open(filepath).convert('RGB')
  print(o.mode, o.size, o.format, filepath)

  w = 1000
  h = int(o.height * w / float(o.width))
  o = o.resize((w, h))
  o = adjust(o, color=1.0, contrast=1.0, brightness=1.0)

  wp = 800
  hp = int(o.height * wp / float(o.width))
  preview = ImagePreview((wp, hp), o)

  t = threading.Thread(target=render, args=(filepath, o, preview))
  t.daemon = True
  t.start()

  # Open the preview window and block the main thread
  preview.start()


if __name__ == '__main__':
  main()
