# Korean_FA: Korean Forced-Aligner  

- v.1.6.2(01.03.21)
- NAMZ Labs


### MacOSX and Linux
---
- Mac OSX 11.0.1(recent Big Sur): Stable.
- Linux (recent Ubuntu 18.04): Stable.
- Windows: Unstable. (Not tested)
- Python 3.5 ~ (python2 is unavailable)


### PREREQUISITE
---
1. **Install Kaldi**
	- Type below in command line.
		```
		$ git clone https://github.com/kaldi-asr/kaldi.git kaldi --origin upstream
		$ cd kaldi
		$ git pull
		``` 
 	- Read INSTALL and follow the direction written there.

2. **Install Packages**
 	- Install list: Sox, coreutils, xlrd.
	-  On mac

		```
		$ brew install sox
		$ brew install coreutils
		$ pip3 install xlrd 
    	```
	- On Ubuntu
	
		```
		apt-get install sox
		apt-get install coreutils
		pip3 install xlrd
		```

### MATERIALS (Data Preparation)
---
1. **Audio files (.wav)** (of sampling rate at 16,000Hz)
	- Please provide audio file(s) in WAV format ('.wav') at 16,000Hz sampling rate.
	- Korean_FA is applied assuming that the sampling rate of input audio file(s) is 16,000Hz.
2. **Text files (.txt)**
	- Name your transcription text files suffixed by ordered numbers
		- ex) name01.txt, name02.txt, ...
	- Each text file should contain one full sentence.
	- **DO NOT** include any punctuation marks such as a period ('.') or a comma (',') in the text file.
	- Sentences should be written in Korean letters.
	- Remove every white space (or tab) in the end of the line.
	- Recommendations for better performance:
	- Less usage of white spaces between characters is strongly recommended.
	- Leave spaces between words in the transcription according to the way the speaker reads. Strict compliance with prescriptive spacing rules is not recommended.
		- i.e. Put a whitespace when a pause is present.
		- ex) If a speaker reads: "나는 그시절 사람들과 사는것이 좋았어요"
		   - Bad example: 나는 그 시절 사람들과 사는 것이 좋았어요
		   - Good example: 나는 그시절 사람들과 사는것이 좋았어요

### DIRECTION
---
1. Navigate to 'Korean_FA' directory.
2. Open forced_align.sh with any text editor to specify user path of kaldi directory.
	- Change 'kaldi' name variable. (initial setting: kaldi=/home/kaldi)
3. Run the code with the path of data to forced-align.

	```
	$ bash forced_align.sh (options) (data directory)
	$ bash forced_align.sh -nw ./example/readspeech
	```
 	- Options
	 	1. -h  | --help    : Showing instruction.
	 	2. -nj | --num-job : Parallel alignment to speed up.
	 	3. -s  | --skip    : Skip alignment for already aligned data.
	 	4. -nw | --no-word : Deleting word tier.
	 	5. -np | --no-phone: Deleting phone tier.

4. Textgrid(s) will be saved into a data directory.

### NOTICE
---
1. **DO NOT** copy or use audio files in the example directory for other purposes.
2. Report bugs or provide any recommendation to us through the developer's email address.

### DEVELOPER
---

- [Hyungwon Yang](https://hyungwonsnotebook.blogspot.kr/) / hyung8758@gmail.com

### CONTRIBUTORS
---
In order to improve forced alignment performance, all contributors named below participate in this project.

#### Coworkers
- Jaekoo Kang / jaekoo.jk@gmail.com
- Yejin Cho / scarletcho@korea.ac.kr
- Yeonjung Hong / yvonne.yj.hong@gmail.com
- Youngsun Cho / youngsunhere@gmail.com
- Sung Hah Hwang / hshsun@gmail.com

#### Advisor
- [Hosung Nam](http://www.haskins.yale.edu/staff/nam.html)


### VERSION HISTORY
---
- v.1.0(08/27/16): gmm, sgmm_mmi, and dnn based Korean FA is released.
- v.1.1(09/06/16): g2p updated. monophone model is added.
- v.1.2(10/10/16): phoneset is simplified. Choosing model such as dnn or gmm for forced alignment is no longer available. 
- v.1.3(10/24/16): Selecting specific labels in TextGrid is available. Procedure of alignment is changed. Audio files collected in the directory will be aligned one by one. Due to this change, alignment takes more time, but its accuracy is increased. Log directory will show the alignment process in detail. More useful information is provided during alignment on the command line. 
- v.1.4(01.14.16): It will catch more errors. The name of log files will be tagged with respect to each wave file name. 
- v.1.5(02.08.17): Main g2p was changed and it is now compatible with the new g2p system. Skipping option is added and it will skip alignment of audio files that have TextGrdis. A few minor bugs are fixed.
- v.1.5.1(02.26.17): bug reports. Time mismatch in the word tier. fixed.
- v.1.5.2(05.17.17): change return to exit, option errors, minor bug fixed. skip option is added.
- v.1.5.3(07.10.17): Long audio files are now available to be aligned. print more information on the screen. Floating error which caused time mismatch betweeen start and end points of each phone segment is fixed.
- v.1.5.4(11.14.17): Floatting error is occurred in kaldi code. This error will be solved as post-processing. Hopely, from now on, time mismatch error will not appear any longer.
- v.1.6(01.18.18): num-jb option is provided and this option will split multiple files into sub groups and align multiple files at once. This will speed up the alignment process. The way of printing log histories and the structure of main script are changed.
- v.1.6.1(10.28.20): lexicon process was unstable and it has been fixed. remove redundant jobs in main_fa.sh and fa_prep_data.sh. 
- **v1.6.2(01.03.21)**: adjust audio process part(sr=16000, channel=1, bit=16) and change log variables. 
