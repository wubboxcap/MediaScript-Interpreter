from json import load, loads
import math
import asyncio
import os
from urllib.parse import urlparse
import urllib.request
import time
from typing import Union
from .text_gen import generate_text
import shutil
import tempfile
class IscriptError(Exception):
    """Exception raised for invalid iscript commands."""
    pass
class DownloadError(Exception):
    """Exception raised for download errors."""
    pass
def _download_logic(url, destination, chunk_size=8192):
    """The blocking logic that runs in a separate thread."""
    try:
        # Define a custom User-Agent to avoid being blocked by servers
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(url, headers=headers)
        
        with urllib.request.urlopen(req) as response:
            # Open the local file for writing in binary mode
            with open(destination, 'wb') as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

async def download_video_async(url, filename):
    """The async wrapper to be called from your event loop."""
    print(f"Starting download: {url}")
    
    # Run the blocking download in a background thread
    success = await asyncio.to_thread(_download_logic, url, filename)
    
    if success:
        print(f"Finished: {filename}")
    else:
        print(f"Failed to download: {filename}")
    return success
async def ffmpeg_process(input_file:str, output_file:str, ffmpeg_args:Union[list,str]):
  """
  Does a asynchronous FFmpeg process.
  
  :param input_file: The input media file.
  :type input_file: str
  :param output_file: The output media file.
  :type output_file: str
  :param ffmpeg_args: The ffmpeg arguments to use.
  :type ffmpeg_args: Union[list,str]
  """
  process = await asyncio.create_subprocess_exec(
    'ffmpeg',
    '-i', input_file,
    *ffmpeg_args if isinstance(ffmpeg_args, list) else [ffmpeg_args],
    output_file,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
  )
  stdout, stderr = await process.communicate()
  if process.returncode != 0:
    raise SystemError(f"FFmpeg process failed with error: {stderr.decode()}")
  pass
async def generate_hue_ppm(hue:str, output_file:str):
  """
  Does a asynchronous ImageMagick process to generate a hue ppm.
  
  :param hue: The hue of the ppm.
  :type hue: float
  :param output_file: The output media file.
  :type output_file: str
  """
  process = await asyncio.create_subprocess_exec(
    'magick',
    'hald:6',
    '-modulate',
    f'100,100,{100+(hue/1.8)}',
    f'{output_file}_{hue}.ppm',
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
  )
  stdout, stderr = await process.communicate()
  if process.returncode != 0:
    raise SystemError(f"Magick process failed with error: {stderr.decode()}")
  pass
  return f'{output_file}_{hue}.ppm'
def evaluate_expression(expression: str, variables: dict):
    """Safely evaluates math, using the variables dict for lookups."""
    # Combine math constants (pi, etc) with your custom variables
    allowed_names = {k: v for k, v in vars(math).items() if not k.startswith("__")}
    allowed_names.update(variables)
    
    try:
        # We use variables as the 'globals' for the eval context
        return eval(expression, {"__builtins__": {}}, allowed_names)
    except Exception as e:
        # If it's not a math expression (like a string path), return as is
        return expression
async def get_media_info(filename: str, info_type: str):
    """Fetches metadata using ffprobe, specifically targeting video streams."""
    # Duration is in 'format', width/height are in 'streams'
    is_duration = info_type == "duration"
    
    args = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0', # Select first video stream only
        '-show_entries', f"{'format' if is_duration else 'stream'}={info_type}",
        '-of', 'json', filename
    ]
    
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await process.communicate()
    data = loads(stdout)
    
    try:
        if is_duration:
            return float(data['format']['duration'])
        # Access the stream that was explicitly selected via v:0
        return int(data['streams'][0][info_type])
    except (KeyError, IndexError):
        print(f"Warning: Could not find {info_type} for {filename}")
        return 0

async def parse(code:str,playoutput:bool=False):
  """
  Docstring for parse
  
  :param code: The iscript code to parse.
  :type code: str
  :param playoutput: Whether to play the output after processing.
  :type playoutput: bool
  """
  start_time = time.time()
  
  # Save original directory before any changes
  original_dir = os.getcwd()
  
  # Create a temporary directory for processing
  temp_dir = tempfile.mkdtemp()
  
  try:
    # Change to temp directory for all processing
    os.chdir(temp_dir)
    
    script_dir = os.path.dirname(__file__)
    json_file_path = os.path.join(script_dir, '../data', 'commands.json')
    with open(json_file_path, 'r') as file:
      commands = load(file)
      command_names = []
      for c in commands:
        command_names.append(c["name"])
    variables = {}
    attachments = []
    medias = []
    def get_media_by_name(name:str):
      for media in medias:
        if media["name"] == name:
          return media["file"]
    def resolve_alias(cmd_name: str):
      """Resolve command aliases to their actual command names."""
      for cmd in commands:
        if cmd["name"] == cmd_name:
          return cmd_name
        if "aliases" in cmd:
          if cmd_name in cmd["aliases"]:
            return cmd["name"]
      return cmd_name
    def rename_new_and_delete_old(new:str,old:str):
      try:
        os.remove(old)
        os.rename(new, old)
      except Exception as e:
        print(f"An error occurred while renaming and deleting files: {e}")
    def resolve_path(file_path: str) -> str:
      """Convert relative paths to absolute paths using original_dir."""
      if os.path.isabs(file_path):
        return file_path
      return os.path.join(original_dir, file_path)
    for line in code.splitlines():
      if not line.strip() or line.startswith("#"):
          continue
      parts = line.split()
      cmd_name = parts[0]
      # Resolve alias to actual command name
      cmd_name = resolve_alias(cmd_name)
      if cmd_name not in command_names:
          raise IscriptError(f"{cmd_name} is not a valid command.")
      cmd_def = next((c for c in commands if c["name"] == cmd_name), None)
      num_args = len(cmd_def["args"])
      parameters = line.split(maxsplit=num_args)
      if cmd_name == "set":
        # set var_name expression
        var_name = parts[1]
        expr = " ".join(parts[2:])
        variables[var_name] = evaluate_expression(expr, variables)
        continue
      elif cmd_name == "get":
        # get media_name property target_var
        m_name, prop, target_var = parts[1], parts[2], parts[3]
        file_path = next((m["file"] for m in medias if m["name"] == m_name), None)
        if file_path:
          variables[target_var] = await get_media_info(file_path, prop)
        continue
      elif cmd_name == "load":
        try:
          if len(parameters) < 2:
            raise IscriptError("load command requires at least a URL")
              
          # Use 'url' instead of the undefined 'arg'
          url = parameters[1]
          parsed_path = urlparse(url).path
          filename = os.path.basename(parsed_path)
          if not filename:
            filename = f"video_{int(time.time())}.mp4"
              
          # Now actually call the download
          await download_video_async(url, filename)
              
          friendly_name = parameters[2] if len(parameters) > 2 else filename
          medias.append({"file": filename, "name": friendly_name})
        except Exception as e:
          print(str(e))
      elif cmd_name == "loadfile":
        try:
          if len(parameters) < 2:
            raise IscriptError("loadfile command requires at least a file path")
              
          # Resolve the file path to absolute path using original directory
          file_path = resolve_path(parameters[1])
          # clone file so that all previous data is not erased
          dest_filename = f"loaded_{int(time.time())}_{os.path.basename(file_path)}"
          shutil.copy2(file_path, dest_filename)
          friendly_name = parameters[2] if len(parameters) > 2 else os.path.basename(file_path)
          medias.append({"file": dest_filename, "name": friendly_name})
        except Exception as e:
          print(str(e))
      elif cmd_name == "tti":
        
          if len(parameters) < 2:
            raise IscriptError("tti command requires at least a URL")
              
          # Use 'url' instead of the undefined 'arg'
          m_name = parts[1]
          size = float(evaluate_expression(parts[2], variables))
          bounds = float(evaluate_expression(parts[3], variables))
          color = parameters[4]
          text = parameters[5]
          filename = f"tti_{m_name}_{int(time.time())}.png"
          generate_text(text,filename,size,color,bounds,"center")
          friendly_name = parameters[1] if len(parameters) > 1 else filename
          medias.append({"file": filename, "name": m_name})
      elif cmd_name == "invert":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for invert.")
              
        output_media = f"invert_{input_media}"
        # ffmpeg args
        args = ["-vf", "negate"]
              
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "clone":
          # Format: clone original_name new_name
          original_name = parts[1]
          new_name = parts[2]
          
          # Find the original file path
          original_file = get_media_by_name(original_name)
          
          if not original_file:
              raise IscriptError(f"Media '{original_name}' not found for cloning.")
              
          # Create a unique filename for the copy
          file_ext = os.path.splitext(original_file)[1]
          new_filename = f"clone_{int(time.time())}_{new_name}{file_ext}"
          
          try:
              # Physically copy the file
              shutil.copy2(original_file, new_filename)
              # Add to the medias list
              medias.append({"file": new_filename, "name": new_name})
          except Exception as e:
              print(f"Cloning Error: {e}")
      elif cmd_name == "join":
        # get filename
        input_media = get_media_by_name(parameters[1])
        input_media2 = get_media_by_name(parameters[2])
        print(input_media2)
        print(input_media)
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
        if not input_media2:
          raise IscriptError(f"Media '{parameters[2]}' not found for reverse.")
        output_media = f"aputmix_{input_media}"
        # ffmpeg args
        if parameters[3].lower() == "true":
          args = ["-i",input_media2,"-filter_complex", f"[0:v][1:v]vstack=inputs=2[v];[0:a][1:a]amix=2:duration=shortest[a]","-map","[v]","-map","[a]"]
        else:
          args = ["-i",input_media2,"-filter_complex", f"[0:v][1:v]hstack=inputs=2[v];[0:a][1:a]amix=2:duration=shortest[a]","-map","[v]","-map","[a]"]

        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "convert":
          # Format: convert media_name audio/wav
          media_name = parts[1]
          mime_type = parts[2]
          
          # Simple mapping of MIME types to extensions
          mime_map = {
              "audio/wav": ".wav",
              "audio/mpeg": ".mp3",
              "audio/ogg": ".ogg",
              "video/mp4": ".mp4",
              "video/x-matroska": ".mkv",
              "image/png": ".png",
              "image/jpeg": ".jpg"
          }
          
          target_ext = mime_map.get(mime_type)
          if not target_ext:
              # Fallback: try to extract the subtype (e.g., 'wav' from 'audio/wav')
              target_ext = f".{mime_type.split('/')[-1]}"

          input_file = get_media_by_name(media_name)
          if not input_file:
              raise IscriptError(f"Media '{media_name}' not found for conversion.")

          output_file = f"conv_{int(time.time())}{target_ext}"
          
          # FFmpeg handles the conversion automatically based on the output extension
          # We use -q:a 0 for variable bitrate audio or -preset fast for video
          args = ["-q:a", "0", "-preset", "fast"]
          
          try:
              await ffmpeg_process(input_file, output_file, args)
              # Replace the reference in the media list with the new file
              for m in medias:
                  if m["name"] == media_name:
                      m["file"] = output_file
          except Exception as e:
              print(f"Conversion Error: {e}")
      
      elif cmd_name == "overlay":
          # Format: overlay base_name top_name x_expr y_expr
          base_name = parts[1]
          top_name = parts[2]
          
          # Evaluate math expressions for coordinates
          x_val = evaluate_expression(parts[3] or "0", variables)
          y_val = evaluate_expression(parts[4] or "0", variables)
          
          base_file = get_media_by_name(base_name)
          top_file = get_media_by_name(top_name)
          
          if not base_file or not top_file:
              raise IscriptError(f"Media not found for overlay: {base_name} or {top_name}")
              
          output_file = f"overlay_{int(time.time())}.mp4"
          
          # FFmpeg command: [0:v][1:v]overlay=x:y
          args = [
              "-i", top_file, 
              "-filter_complex", f"[0:a][1:a]amix=2:duration=shortest[a];[0:v][1:v]overlay={x_val}:{y_val}[v]",
              "-map", "[v]",
              "-map", "[a]"
          ]
          
          try:
              await ffmpeg_process(base_file, output_file, args)
              # Replace the base media with the new overlaid version
              rename_new_and_delete_old(output_file, base_file)
          except Exception as e:
              print(f"Overlay Error: {e}")
      elif cmd_name == "rotate":
          # Format: rotate media_name degrees background_color crop
          input_media = get_media_by_name(parameters[1])
          degrees = float(evaluate_expression(parts[2], variables))
          background_color = parts[3] or "black"
          crop = parts[4].lower() == "true"

          if not input_media:
              raise IscriptError(f"Media not found for rotate: {parameters[1]}")

          output_file = f"rotate_{int(time.time())}.mp4"

          # FFmpeg command: -vf "rotate=PI/4:ow='ceil(iwcos(PI/4)+ihsin(PI/4))':oh='ceil(iwsin(PI/4)+ihcos(PI/4))'" ./output/output.mp4
          widths = ":ow='ceil(iw*cos(PI/4)+ih*sin(PI/4))':oh='ceil(iw*sin(PI/4)+ih*cos(PI/4))'" if not crop else ""
          args = [
              "-vf", f"rotate={math.radians(degrees)}{widths}:c={background_color}"
          ]

          try:
              await ffmpeg_process(input_media, output_file, args)
              # Replace the base media with the new overlaid version
              rename_new_and_delete_old(output_file, input_media)
          except Exception as e:
              print(f"Overlay Error: {e}")
      elif cmd_name == "reverse":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
            
        output_media = f"reversed_{input_media}"
        # ffmpeg args
        args = ["-vf", "reverse", "-af", "areverse"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "speed":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
            
        output_media = f"speed_{input_media}"
        # ffmpeg args
        args = ["-vf", f"setpts=1/{parameters[2]}*PTS,fps=30", "-af", f"rubberband=tempo={parameters[2]}:formant=712923000"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "hueshifthsv":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for hueshifthsv.")
            
        output_media = f"hueshifthsv_{input_media}"
        output_hue = f"hue_{int(time.time())}"
        hue = await generate_hue_ppm(float(parameters[2]),output_hue)
        args = ["-vf", f"movie={hue},[in]haldclut,format=yuv420p"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "swirl":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for swirl.")
        w, h = await get_media_info(input_media, "width"), await get_media_info(input_media, "height")
        output_media = f"swirl_{input_media}"
        swirl_value = float(evaluate_expression(parameters[2],variables))
        # ffmpeg args
        args = ["-vf", f"format=yuv444p,scale={h}:{h},geq='p(W*0.5+(hypot(X-W*0.5,Y-H*0.5)+1e-6)*cos((atan2(Y-H*0.5,X-W*0.5))+(({swirl_value})/180*PI)*(if(lt(hypot(X-W*0.5,Y-H*0.5)+1e-6,min(W,H)*0.5),1-(hypot(X-W*0.5,Y-H*0.5)+1e-6)/(min(W,H)*0.5),0)^2)),H*0.5+(hypot(X-W*0.5,Y-H*0.5)+1e-6)*sin((atan2(Y-H*0.5,X-W*0.5))+(({swirl_value})/180*PI)*(if(lt(hypot(X-W*0.5,Y-H*0.5)+1e-6,min(W,H)*0.5),1-(hypot(X-W*0.5,Y-H*0.5)+1e-6)/(min(W,H)*0.5),0)^2)))',scale={w}:{h},setsar=1:1,format=yuv420p"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "explode":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for explode.")
        w, h = await get_media_info(input_media, "width"), await get_media_info(input_media, "height")
        output_media = f"explode_{input_media}"
        try:
          float(evaluate_expression(parameters[2], variables))
        except IndexError: # if 2nd parameter does not exist or is invalid, default to 1
          explode_value = 1
        # ffmpeg args
        args = ["-vf", f"format=yuv444p,scale={h}:{h},geq='p((W*0.5)+(X-W*0.5)/(lte((hypot(X-W*0.5,Y-H*0.5)),(min(W,H)*0.5))*(1+({explode_value})*2*atan(atan(atan(atan(1-(hypot(X-W*0.5,Y-H*0.5))/(min(W,H)*0.5))^2))))+gt((hypot(X-W*0.5,Y-H*0.5)),(min(W,H)*0.5))*1),(H*0.5)+(Y-H*0.5)/(lte((hypot(X-W*0.5,Y-H*0.5)),(min(W,H)*0.5))*(1+({explode_value})*2*atan(atan(atan(atan(1-(hypot(X-W*0.5,Y-H*0.5))/(min(W,H)*0.5))^2))))+gt((hypot(X-W*0.5,Y-H*0.5)),(min(W,H)*0.5))*1))',scale={w}:{h},setsar=1:1,format=yuv420p"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "flip":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for flip.")
            
        output_media = f"flip_{input_media}"
        # ffmpeg args
        args = ["-vf","vflip"]
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "flop":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for flop.")
            
        output_media = f"flop_{input_media}"
        # ffmpeg args
        args = ["-vf","hflip"]
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "haah":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
            
        output_media = f"haah_{input_media}"
        # ffmpeg args
        args = ["-vf","crop=iw/2:ih:0:0,split[left][tmp];[tmp]hflip[right];[left][right]hstack"]
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "waaw":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
            
        output_media = f"waaw_{input_media}"
        # ffmpeg args
        args = ["-vf","crop=iw/2:ih:iw/2:0,split[right][tmp];[tmp]hflip[left];[left][right]hstack"]
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "woow":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
            
        output_media = f"woow_{input_media}"
        # ffmpeg args
        args = ["-vf","crop=iw:ih/2:0:0,split[top][tmp];[tmp]vflip[bottom];[top][bottom]vstack"]
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "hooh":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
            
        output_media = f"hooh_{input_media}"
        # ffmpeg args
        args = ["-vf","crop=iw:ih/2:0:ih/2,split[bottom][tmp];[tmp]vflip[top];[top][bottom]vstack"]
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "contrast":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
            
        output_media = f"contrast_{input_media}"
        contrast = float(evaluate_expression(parameters[2],variables))
        # ffmpeg args
        args = ["-vf", f"eq=contrast={contrast}"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "brightness":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for brightness.")
            
        output_media = f"brightness_{input_media}"
        brightness = float(evaluate_expression(parameters[2],variables))
        # ffmpeg args
        args = ["-vf", f"eq=brightness={max(brightness, 0)}"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "darken":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")

        output_media = f"darken_{input_media}"
        brightness = -float(evaluate_expression(parameters[2],variables))
        # ffmpeg args
        args = ["-vf", f"eq=brightness={max(brightness, -100)}"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "blur":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for blur.")
            
        output_media = f"blur_{input_media}"
        scale = float(evaluate_expression(parameters[2],variables))
        # ffmpeg args
        args = ["-vf", f"boxblur={scale}"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "volume":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
            
        output_media = f"volume_{input_media}"
        vol = float(evaluate_expression(parameters[2],variables))
        # ffmpeg args
        args = ["-af", f"volume={vol}"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "volume":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
            
        output_media = f"volume_{input_media}"
        vol = float(evaluate_expression(parameters[2],variables))
        # ffmpeg args
        args = ["-af", f"volume={vol}"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "audiopitch":
        # get filename
        input_media = get_media_by_name(parameters[1])
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
            
        output_media = f"apitch_{input_media}"
        pitch = float(evaluate_expression(parameters[2],variables))
        # ffmpeg args
        args = ["-af", f"rubberband=pitch={pitch}:formant=712923000"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      elif cmd_name == "audioputmix":
        # get filename
        input_media = get_media_by_name(parameters[1])
        input_media2 = get_media_by_name(parameters[2])
        print(input_media2)
        print(input_media)
        if not input_media:
          raise IscriptError(f"Media '{parameters[1]}' not found for reverse.")
        if not input_media2:
          raise IscriptError(f"Media '{parameters[2]}' not found for reverse.")
        output_media = f"aputmix_{input_media}"
        # ffmpeg args
        args = ["-i",input_media2,"-filter_complex", f"[0:a][1:a]amix=2:duration=shortest[a]","-map","0:v","-map","[a]"]
            
        try:
          # call ffmpeg
          await ffmpeg_process(input_media, output_media, args)
          rename_new_and_delete_old(output_media, input_media)
        except Exception as e:
          print(f"FFmpeg Error: {e}")
          break
      
      elif cmd_name == "render":
        media = get_media_by_name(parameters[1])
        attachments.append({"file":media,"name":parameters[2] or parameters[0]})
        break
    # if no render command found, return first media loaded in attachments
    if not attachments:
      if medias:
        first_media = medias[0]
        attachments.append({"file":first_media["file"],"name":first_media["name"]})
    
    end_time = time.time()
    
    # Copy final attachments to original directory
    final_attachments = []
    for attachment in attachments:
      temp_file = attachment["file"]
      # Create output filename in original directory
      final_filename = os.path.join(original_dir, os.path.basename(temp_file))
      shutil.copy2(temp_file, final_filename)
      final_attachments.append({"file": final_filename, "name": attachment["name"]})
    
    if playoutput:
      for attachment in final_attachments:
        # os.startfile(attachment["file"])
        # use ffplay to play the file
        process = await asyncio.create_subprocess_exec(
          'ffplay',
          '-autoexit',
          attachment["file"],
          stdout=asyncio.subprocess.PIPE,
          stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()
    
    return {"time":end_time - start_time,"attachments":final_attachments}
  
  finally:
    # Always clean up: return to original directory and remove temp directory
    os.chdir(original_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)

def get_commands() -> list:
  """
  Returns the list of available commands.
  
  :return: The list of commands.
  :rtype: list
  """
  script_dir = os.path.dirname(__file__)
  json_file_path = os.path.join(script_dir, '../data', 'commands.json')
  with open(json_file_path, 'r') as file:
    commands = load(file)
  return commands
def commandlength():
  """
  Returns the number of available commands.
  
  :return: The number of commands.
  :rtype: int
  """
  script_dir = os.path.dirname(__file__)
  json_file_path = os.path.join(script_dir, '../data', 'commands.json')
  with open(json_file_path, 'r') as file:
    commands = load(file)
  return len(commands)
def get_commands() -> list:
  """
  Returns the list of available commands.
  
  :return: The list of commands.
  :rtype: list
  """
  script_dir = os.path.dirname(__file__)
  json_file_path = os.path.join(script_dir, '../data', 'commands.json')
  with open(json_file_path, 'r') as file:
    commands = load(file)
  return commands
def commandlength():
  """
  Returns the number of available commands.
  
  :return: The number of commands.
  :rtype: int
  """
  script_dir = os.path.dirname(__file__)
  json_file_path = os.path.join(script_dir, '../data', 'commands.json')
  with open(json_file_path, 'r') as file:
    commands = load(file)
  return len(commands)