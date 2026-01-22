# MediaScript Interpreter

A Python implementation of the MediaScript interpreter—a powerful domain-specific language for media manipulation and processing. This interpreter supports a wide range of image and audio operations, including transformations, filters, effects, and concatenation.

## Features

- **Image Processing**: Blur, brightness, contrast, rotation, cropping, filters, and more
- **Audio Processing**: Volume, pitch, compression, bass boosting, and audio mixing
- **Media Manipulation**: Loading, rendering, concatenation, overlaying, and format conversion
- **Variable Support**: Store and manipulate media and values throughout scripts
- **Chainable Operations**: Compose complex media workflows through sequential commands

## Installation

### Requirements
#### Python
- Python 3.7+
- Pillow (PIL)
#### Packages
- [FFmpeg](https://ffmpeg.org/download.html)
- [ImageMagick](https://imagemagick.org/script/download.php#gsc.tab=0)
### Setup

1. Clone the repository:
```bash
git clone https://github.com/wubboxcap/MediaScript-Interpreter.git
cd MediaScript-Interpreter
```

2. Install dependencies:
```bash
pip install -r MediaScript/requirements.txt
```

## Quick Start

### Basic Usage

```python
from MediaScript import parse
import asyncio

# Define a MediaScript program
script = """
loadfile input.png image
brightness image 50
invert image
render image output
"""

# Execute the script
results = asyncio.run(parse(script, playoutput=True)) # Playoutput plays the video after processing in a seperate window.
print(results)
```

### Example Script

See [examplescripts/gm74.py](examplescripts/gm74.py) for a complete example that loads a video file, applies various filters and audio effects, and renders the output.

## Commands

MediaScript supports dozens of commands for media manipulation:

### Image Commands
- `brightness` - Adjust image brightness
- `contrast` - Adjust contrast levels
- `blur` - Apply blur filter
- `invert` - Invert colors
- `grayscale` - Convert to grayscale
- `pixelate` - Pixelate effect
- `deepfry` - Deep fry effect
- `crop` - Crop image
- `flip` / `flop` - Flip or flop image
- And many more...

### Audio Commands
- `audiopitch` - Adjust pitch
- `audioboostbass` - Boost bass
- `audiocompress` - Compress audio
- `audioputmix` - Mix audio tracks
- `audioputconcat` - Concatenate audio
- `audioputreplace` - Replace audio

### Media Commands
- `load` / `loadfile` - Load media from URL or file
- `clone` / `copy` - Clone media to new variable
- `concat` - Concatenate media
- `overlay` - Overlay media on another
- `join` - Join two media files
- `render` - Render and save output
- `convert` - Convert media format

For a complete list of available commands, see [MediaScript/iscript_commands.txt](MediaScript/iscript_commands.txt) or [MediaScript/data/commands.json](MediaScript/data/commands.json).

## Project Structure

```
MediaScript-Interpreter/
├── MediaScript/
│   ├── __init__.py          # Main module entry point
│   ├── requirements.txt      # Python dependencies
│   ├── iscript_commands.txt # Command documentation
│   ├── parser/
│   │   ├── parse.py         # Script parser
│   │   └── text_gen.py      # Text generation utilities
│   └── data/
│       └── commands.json    # Command definitions
├── examplescripts/
│   └── gm74.py             # Example usage script
└── README.md               # This file
```

## Usage

### In Code

```python
from MediaScript import parse
import asyncio

# Single-line command
script = "create image 800 600"

# Execute
results = asyncio.run(parse(script))
```

### Variables

Store and reference media throughout your script:

```
loadfile photo.jpg img
brightness img 20
contrast img 10
render img output.jpg
```

## Architecture

The interpreter consists of:

- **Parser** (`parser/parse.py`) - Parses MediaScript commands and manages execution
- **Commands** - Executed through a plugin-like system defined in `commands.json`
- **Media Handler** - Manages loaded media and rendering

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

This is a Python port of the MediaScript interpreter from NotSoBot.
