

import librosa
import numpy as np
import matplotlib.pyplot as plt
from moviepy import VideoFileClip, concatenate_videoclips
import os
from functools import partial
import soundfile as sf
import sys
import shutil
import multiprocessing
import argparse
from pathlib import Path


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
    energy = librosa.feature.rms(
        y=y, frame_length=frame_length, hop_length=hop_length)
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


def get_energy_thres(all_energies):
    index_at_four_ninths = int(len(all_energies) * 4 / 9)
    return np.sort(all_energies)[index_at_four_ninths]


def plot_energy(time, energy, output_path='plot.png', tick_interval=20):
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

def unoverlap_segments(segments):
    segments.sort(key=lambda x: x[0])
    
    merged_segments = []
    for segment in segments:
        if not merged_segments:
            merged_segments.append(segment)
        else:
            last_start, last_end = merged_segments[-1]
            current_start, current_end = segment
            
            if last_end >= current_start:
                merged_segments[-1] = (last_start, max(last_end, current_end))
            else:
                merged_segments.append(segment)
    
    return merged_segments

def trim_video(input_video_path, output_video_path, energy, time, energy_threshold=0.008, min_duration=3.0, start_buffer=0.8, end_buffer=0.6):
    with VideoFileClip(input_video_path) as video:
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
                
        segments = unoverlap_segments(segments)
        clips = [video.subclipped(max(0, start), min(
            video_duration, end)) for start, end in segments]
        
        final_clip = concatenate_videoclips(clips)
        final_clip.write_videofile(
            output_video_path)
        final_clip.close()

        print(f"{len(segments)} segments for {input_video_path} were found.")
        print("segment for {input_video_path}", segments)

        return len(segments), video.duration


def calculate_removed_percentage(removed_time, total_time):
    return (removed_time / total_time) * 100


def plot_energy_statistics(all_energies, output_path):
    intervals = [i * 0.001 for i in range(41)]
    counts = [sum(1 for energy in all_energies if energy <= interval)
              for interval in intervals]

    plt.figure(dpi=300)

    plt.plot(intervals, counts, marker='o', linestyle='-', color='b')

    plt.title('Energy Statistics')
    plt.xlabel('Interval Point')
    plt.ylabel('Number of Energies <= Interval Point')

    plt.grid(True)

    plt.savefig(output_path)


def process_video(input_video_path, output_video_path, segment_duration=200.0, is_debug=None):
    sample_name = os.path.splitext(os.path.basename(input_video_path))[0]

    temp_audio_dir = f"./temp_audio_segments_match_{sample_name}"
    os.makedirs(temp_audio_dir, exist_ok=True)

    print(f"extracting and splitting audio for {sample_name}...")
    audio_path = f"./temp_audio_segments_match_{sample_name}.wav"
    os.system(
        f"ffmpeg -i {input_video_path} -vn -acodec pcm_s16le {audio_path}")

    _, sr = librosa.load(audio_path, sr=None)

    segments = split_audio(audio_path, segment_duration, temp_audio_dir)

    print(f"extracting energy from segments for {sample_name}...")
    segments_data = []
    for i, segment in enumerate(segments):
        print(
            f"processing {input_video_path} segment {i+1}/{len(segments)}...")
        segment_data = extract_energy_segment(segment)
        segments_data.append(segment_data)

    print(f"merging energy data for {sample_name}...")
    all_times, all_energies = merge_energy_data(segments_data, sr)
    print(f"length of merged energy array for {sample_name}: ", len(
        all_energies))

    if is_debug is not None:
        print(f"plotting energy along with time for {sample_name}...")
        plot_energy(all_times, all_energies,
                    output_path=f'plot_energy_{sample_name}.png')

        print(f"plotting the dist. of energy data for {sample_name}...")
        plot_energy_statistics(
            all_energies, output_path=f'plot_dist_{sample_name}.png')

    energy_threshold = get_energy_thres(all_energies)
    print(f"The energy threshold for {sample_name}: {energy_threshold}")

    print(f"trimming video for {sample_name}...")
    segments, _ = trim_video(input_video_path, output_video_path,
                             all_energies, all_times, energy_threshold=energy_threshold)

    print(f"cleaning up temporary files and directory for {sample_name}...")
    os.remove(audio_path)
    for segment_file in os.listdir(temp_audio_dir):
        segment_path = os.path.join(temp_audio_dir, segment_file)
        os.remove(segment_path)
    shutil.rmtree(temp_audio_dir)

    print(f"Done for {sample_name}.")


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, required=True)
    parser.add_argument('--output', type=str)
    parser.add_argument('--debug',  nargs='*')

    args = parser.parse_args()

    input_file = args.input
    output_file = args.output
    is_debug = args.debug

    output_file_name = f"{Path(input_file).stem}_clipped{Path(input_file).suffix}"

    if output_file is None:
        output_file = os.path.join(
            Path(input_file).parent, output_file_name)
    elif Path(output_file).is_dir():
        output_file = os.path.join(output_file, output_file_name)
    else:
        pass

    os.makedirs(Path(output_file).parent, exist_ok=True)

    process_video(input_video_path=input_file,
                  output_video_path=output_file, is_debug=is_debug)


if __name__ == "__main__":
    main()
