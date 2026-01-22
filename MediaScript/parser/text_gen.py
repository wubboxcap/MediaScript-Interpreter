from PIL import Image, ImageDraw, ImageFont
import os

def get_font_path():
    """Detects standard font paths for Termux/Android/Linux."""
    paths = [
        "/system/fonts/Roboto-Regular.ttf",
        "/system/fonts/DroidSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for p in paths:
        if os.path.exists(p): return p
    return None

def wrap_text_smart(text, font, max_width):
    """Wraps only at spaces. Long words are allowed to exceed max_width."""
    words = text.split(' ')
    lines = []
    current_line = []

    for word in words:
        test_line = ' '.join(current_line + [word])
        # Measure pixel width of the potential line
        if font.getlength(test_line) <= max_width or not current_line:
            current_line.append(word)
        else:
            lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return '\n'.join(lines)

def generate_text(text, output_file="output.png", font_size=50, color="white", wrap_bounds=600, align="left"):
    font_path = get_font_path()
    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    # 1. Wrap the text (Preserving long words)
    wrapped_text = wrap_text_smart(text, font, wrap_bounds)

    # 2. Calculate the bounding box for the entire multiline block
    temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = temp_draw.multiline_textbbox((0, 0), wrapped_text, font=font, align=align)
    
    # Width and height of the visual "ink"
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    # 3. Create image 
    # Note: align affects how lines relate to each other within the bounding box
    img = Image.new("RGBA", (int(w) + 4, int(h) + 4), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 4. Draw text
    # We use anchor="la" (left-top) and offset by negative bbox to strip padding
    # The 'align' parameter handles the internal justification of the lines
    draw.multiline_text((-bbox[0] + 2, -bbox[1] + 2), wrapped_text, font=font, fill=color, align=align)

    # 5. Save
    img.save(output_file)
    print(f"✅ Created {align}-aligned image: {output_file} ({img.size[0]}x{img.size[1]})")