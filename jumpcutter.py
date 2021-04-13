import subprocess
from scipy.io import wavfile
import numpy as np
import re
import math
import os
import argparse
import xml.etree.ElementTree as ET

def getMaxVolume(s):
    maxv = float(np.max(s))
    minv = float(np.min(s))
    return max(maxv,-minv)

def inputToOutputFilename(filename):
    dotIndex = filename.rfind(".")
    return filename[:dotIndex]+"_ALTERED"+filename[dotIndex:]

parser = argparse.ArgumentParser(description='Cuts out silence from videos.')
parser.add_argument('--input_file', type=str,  help='the video file you want modified')
# parser.add_argument('--url', type=str, help='A youtube url to download and process')
parser.add_argument('--output_file', type=str, default="", help="the output file. (optional. if not included, it'll just modify the input file name)")
parser.add_argument('--silent_threshold', type=float, default=0.03, help="the volume amount that frames' audio needs to surpass to be consider \"sounded\". It ranges from 0 (silence) to 1 (max volume)")
# parser.add_argument('--sounded_speed', type=float, default=1.00, help="the speed that sounded (spoken) frames should be played at. Typically 1.")
# parser.add_argument('--silent_speed', type=float, default=5.00, help="the speed that silent frames should be played at. 999999 for jumpcutting.")
parser.add_argument('--frame_margin', type=float, default=1, help="some silent frames adjacent to sounded frames are included to provide context. How many frames on either the side of speech should be included? That's this variable.")
# parser.add_argument('--sample_rate', type=float, default=44100, help="sample rate of the input and output videos")
parser.add_argument('--frame_rate', type=float, help="frame rate of the input and output videos.")
# parser.add_argument('--frame_quality', type=int, default=3, help="quality of frames to be extracted from input video. 1 is highest, 31 is lowest, 3 is the default.")
args = parser.parse_args()

frameRate = args.frame_rate
SILENT_THRESHOLD = args.silent_threshold
INPUT_FILE = args.input_file
FRAME_MARGIN = args.frame_margin

assert INPUT_FILE != None , "I need an input file to process."
assert frameRate != None, "Please specify the original video's frame rate."
    
if len(args.output_file) >= 1:
    OUTPUT_FILE = args.output_file
else:
    OUTPUT_FILE = inputToOutputFilename(INPUT_FILE)

command = "ffmpeg -i "+INPUT_FILE+" -ab 160k -ac 2 -ar 44100 -vn ./jumpcutter_audio.wav"

subprocess.call(command, shell=True)

sampleRate, audioData = wavfile.read("./jumpcutter_audio.wav")
audioSampleCount = audioData.shape[0]
maxAudioVolume = getMaxVolume(audioData)
samplesPerFrame = sampleRate/frameRate
audioFrameCount = int(math.ceil(audioSampleCount/samplesPerFrame))
hasLoudAudio = np.zeros((audioFrameCount))

for i in range(audioFrameCount):
    start = int(i*samplesPerFrame)
    end = min(int((i+1)*samplesPerFrame),audioSampleCount)
    audiochunks = audioData[start:end]
    maxchunksVolume = float(getMaxVolume(audiochunks))/maxAudioVolume
    if maxchunksVolume >= SILENT_THRESHOLD:
        hasLoudAudio[i] = 1

chunks = [[0,0,0]]
shouldIncludeFrame = np.zeros((audioFrameCount))
for i in range(audioFrameCount):
    start = int(max(0,i-FRAME_MARGIN))
    end = int(min(audioFrameCount,i+1+FRAME_MARGIN))
    shouldIncludeFrame[i] = np.max(hasLoudAudio[start:end])
    if (i >= 1 and shouldIncludeFrame[i] != shouldIncludeFrame[i-1]): # Did we flip?
        chunks.append([chunks[-1][1],i,shouldIncludeFrame[i-1]])

chunks.append([chunks[-1][1],audioFrameCount,shouldIncludeFrame[i-1]])
chunks = chunks[1:]

outputAudioData = np.zeros((0,audioData.shape[1]))
outputPointer = 0

etree = ET.Element('mlt')
sprod = ET.SubElement(etree, 'producer', attrib={'id': 'producer0'})
sprop = ET.SubElement(sprod, 'property', attrib={'name': 'resource'})
sprop.text = INPUT_FILE
splay = ET.SubElement(etree, 'playlist', attrib={'id': 'playlist0'})

lastExistingFrame = None
for chunk in chunks:
    outputPointer = chunk[0]
    endPointer = chunk[1]
    if (chunk[2]):
        ET.SubElement(splay,'entry', attrib={'producer':'producer0', 'in': str(chunk[0]), 'out': str(chunk[1])})

ET.ElementTree(etree).write('jumpcutter.mlt')

command = ".\melt jumpcutter.mlt -consumer avformat:"+OUTPUT_FILE
subprocess.call(command, shell=True)