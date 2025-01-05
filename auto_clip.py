import librosa
import numpy as np
import matplotlib.pyplot as plt
from moviepy import VideoFileClip, concatenate_videoclips
import os
from functools import partial
import soundfile as sf
import sys

def split_audio(audio_path, segment_duration, output_dir):
    y, sr = librosa.load(audio_path, sr=None)
    duration = librosa.get_duration(y=y, sr=sr)
    num_segments = int(np.ceil(duration / segment_duration))
    
    segments = []
    for i in range(num_segments):
        start_time = i * segment_duration
        end_time = (i + 1) * segment_duration
        end_time = min(end_time, duration)
        
        segment_y = y[int(start_time * sr):int(end_time * sr)]
        segment_path = os.path.join(output_dir, f"segment_{i}.wav")
        sf.write(segment_path, segment_y, sr)  
        segments.append((segment_path, start_time, end_time - start_time))
    
    return segments

def extract_energy_segment(segment_info):
    segment_path, start_time, duration = segment_info
    frame_length = 20480
    hop_length = 512
    
    y, sr = librosa.load(segment_path, sr=None)
    energy = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)
    time = librosa.times_like(energy, sr=sr, hop_length=hop_length)
    

    adjusted_time = time + start_time
    
    return adjusted_time, energy[0], duration


def merge_energy_data(segments_data, sr):
    all_times = []
    all_energies = []
    
    for times, energy, duration in segments_data:
        all_times.extend(times)
        all_energies.extend(energy)
    
    all_times = np.array(all_times)
    all_energies = np.array(all_energies)
    
    sorted_indices = np.argsort(all_times)
    all_times = all_times[sorted_indices]
    all_energies = all_energies[sorted_indices]
    
    return all_times, all_energies

def plot_energy(time, energy, output_path='match_1212_energy_plot_10xwin.png', tick_interval=20):
    plt.figure(figsize=(10, 6))
    plt.plot(time, energy, label="Short-term Energy")
    plt.xlabel('Time (s)')
    plt.ylabel('Energy')
    plt.title('Short-Term Energy vs Time')
    plt.grid(True)
    
    xticks = np.arange(0, max(time) + 1, tick_interval)
    plt.xticks(xticks, [f"{x:.1f}" for x in xticks])
    
    plt.savefig(output_path)
    plt.close()

def trim_video(input_video_path, output_video_path, energy, time, energy_threshold=0.008, min_duration=3.0, start_buffer=0.8, end_buffer=0.6):
    video = VideoFileClip(input_video_path)
    video_duration = video.duration 
    
    segments = []
    current_start = None
    
    for i in range(len(energy)):
        if energy[i] > energy_threshold:
            if current_start is None:
                current_start = time[i]
        else:
            if current_start is not None:
                current_end = time[i]
                duration = current_end - current_start
                if duration >= min_duration:
                    adjusted_start = max(0, current_start - start_buffer)
                    adjusted_end = current_end + end_buffer
                    segments.append((adjusted_start, adjusted_end))
                current_start = None
    
    if current_start is not None:
        current_end = time[-1]
        duration = current_end - current_start
        if duration >= min_duration:
            adjusted_start = max(0, current_start - start_buffer)
            adjusted_end = min(video_duration, current_end + end_buffer)
            segments.append((adjusted_start, adjusted_end))
    
    clips = [video.subclipped(max(0, start), min(video_duration, end)) for start, end in segments]
    
    final_clip = concatenate_videoclips(clips)
    final_clip.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
    
    return len(segments), video.duration


def calculate_removed_percentage(removed_time, total_time):
    return (removed_time / total_time) * 100

def process_video(input_video_path, output_video_path, segment_duration=200.0):
    temp_audio_dir = "./temp_audio_segments_match_1212"
    os.makedirs(temp_audio_dir, exist_ok=True)
    
    print("extracting and splitting audio...")
    audio_path = "./match_1212_temp_audio.wav"
    os.system(f"ffmpeg -i {input_video_path} -vn -acodec pcm_s16le {audio_path}")
    
    y, sr = librosa.load(audio_path, sr=None)
    
    segments = split_audio(audio_path, segment_duration, temp_audio_dir)
    
    print("extracting energy from segments...")
    segments_data = []
    for i, segment in enumerate(segments):
        print(f"processing segment {i+1}/{len(segments)}...")
        segment_data = extract_energy_segment(segment)
        segments_data.append(segment_data)
    
    print("merging energy data...")
    all_times, all_energies = merge_energy_data(segments_data, sr)
    
    # print("plotting energy...")
    # plot_energy(all_times, all_energies)
    

    print("trimming video...")
    segments, _ = trim_video(input_video_path, output_video_path, all_energies, all_times)
    
    # calculating the deleting time [WIP]
    # removed_time = total_time - sum([end - start for (start, end) in segments])
    # removed_percentage = calculate_removed_percentage(removed_time, total_time)
    # print(f"deleting {removed_percentage:.2f}% time of video.")
    
    # clear temp file [TODO]
    
    




def main():
    if len(sys.argv) != 3:
        print("Usage: python script_name.py input_video output_video")
        sys.exit(1)
    
    input_video = sys.argv[1]
    output_video = sys.argv[2]
    
    segment_duration = 200.0  
    
    process_video(input_video, output_video, segment_duration)
    
    
if __name__ == "__main__":
    main()