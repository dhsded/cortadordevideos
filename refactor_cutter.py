import sys
import os

with open("video_cutter.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
in_process = False

for i, line in enumerate(lines):
    if "for person_name, scenes in scenes_dict.items():" in line:
        new_lines.append("            def process_person_task(person_name, scenes):\n")
        new_lines.append("                if cancel_event and cancel_event.is_set(): return\n")
        new_lines.append("                base_clip_local = VideoFileClip(self.video_path)\n")
        in_process = True
    elif in_process and "subclip = base_clip.subclipped(start_time, end_time)" in line:
        new_lines.append(line.replace("base_clip", "base_clip_local"))
    elif in_process and "if cancel_event and cancel_event.is_set():\n" in line and "break\n" in lines[i+1] and "for" not in lines[i-1] and "while" not in lines[i-1]:
        # we don't want to change break inside the inner loop, only the outer loop
        new_lines.append(line)
    elif in_process and "stats[\"video_render_time\"] += " in line:
        new_lines.append("                            with stats_lock:\n    " + line)
    elif in_process and "stats[\"image_export_time\"] += " in line:
        new_lines.append("                        with stats_lock:\n    " + line)
    elif in_process and "stats[\"photo_extraction_time\"] += " in line:
        new_lines.append("                        with stats_lock:\n    " + line)
    elif in_process and "stats[\"photos_exported\"] += " in line:
        new_lines.append("                        with stats_lock:\n    " + line)
    elif in_process and "processed_persons += 1" in line:
        new_lines.append("                with stats_lock:\n    " + line)
    elif in_process and "stats[\"processed_persons\"] =" in line:
        new_lines.append("                with stats_lock:\n    " + line)
    elif "return stats" in line:
        executor_code = """
            import concurrent.futures
            import threading
            global stats_lock
            stats_lock = threading.Lock()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, (os.cpu_count() or 4) - 1)) as executor:
                futures = [executor.submit(process_person_task, name, sc) for name, sc in scenes_dict.items()]
                concurrent.futures.wait(futures)
                
            base_clip.close()
"""
        new_lines.append(executor_code)
        new_lines.append(line)
    else:
        new_lines.append(line)

with open("video_cutter.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Refactoring done.")
