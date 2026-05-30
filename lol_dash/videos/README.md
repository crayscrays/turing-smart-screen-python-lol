# Idle videos

Drop a `.mp4` file in this folder.

When `lol_dash` starts, it picks the **first `.mp4`** it finds here, converts it
once to a GIF (cached at `lol_dash/assets/idle.gif`), and loops it on the
screen whenever you're not in a League match.

To switch videos:
1. Delete the `.mp4` you don't want
2. Drop the new one in
3. Delete `lol_dash/assets/idle.gif` so it re-converts next launch
   (or just delete it always; re-conversion is fast)

Supported: any MP4 ffmpeg can read. Cropped/scaled to 320×480 portrait at 8fps.

If this folder is empty, the screen stays black during idle (with a log warning).
