# Korean_FA: Korean Forced-Aligner  

- v.1.7.0(09.03.23)

## Docker
- Korean Forced Aligner (Korean_FA) can now be executed within a Docker image. When you run this Docker image, Korean_FA becomes accessible via a user-friendly web interface. This interface enables users to effortlessly upload audio and text pairs and subsequently download the resulting TextGrid files. Please follow the instructions below.
- If Docker is not already installed on your computer system, please download and install it from [Docker's official website.](https://docs.docker.com/desktop/)
### Installation
1. (recommended) pulling a docker image
	- To utilize the recommended method, follow the step in your terminal (macOS, Linux, or Windows WSL).
		```bash
		$ docker pull hyung8758/koreanfa
		```
2. building a docker image
	- To build a Docker image, navigate to the Korean_FA directory and execute the following command.
		```bash
		$ bash ./build.sh
		```
	- Inside the "build.sh" file, you can customize values for the USE_BUILDX and USE_SUDO variables if needed. While running the script as-is should work fine, system-specific errors may occur.
	- Upon successful completion of the building process, you should see "korean_fa_app" listed in the Docker image inventory.
		```bash
		$ docker images # Displays a list of Docker images.
		```
### Usage
- Starting the Container from the Image.
	```bash
	$ docker run -d -p 31066:31066 --name korean_fa_web_server hyung8758/koreanfa
	```
- Once you've executed the command, you can access the Korean_FA web UI at http://localhost:31066
- Stopping a Docker Container.
	```bash
	$ docker stop korean_fa_web_server
	```
- Restarting a Docker Container.
	```bash
	$ docker start korean_fa_web_server
	```
- Removing Korean_FA Container and Image.
	```bash
	$ docker rm korean_fa_web_server # remove a container. ensure it is stopped first.
	$ docker rmi hyung8758/koreanfa # remove an image.
	```

## Local Environment
- It is highly recommended to utilize a Docker image for running the Korean_FA application. Nevertheless, for those who prefer running the application directly in a terminal, please proceed with the following steps.

### OS
- Mac OSX 11.0.1(recent Big Sur): Stable.
- Linux (recent Ubuntu 18.04): Stable.
- Windows: unstable (Not tested)

### Prerequisite
1. Installing Kaldi
	- Type below in command line.
		```bash
		$ git clone https://github.com/kaldi-asr/kaldi.git kaldi --origin upstream
		$ cd kaldi
		$ git pull
		``` 
 	- Read INSTALL and follow the direction written there.

2. Installing Dependencies
	- You will need Python 3.8 or a more recent version. You can achieve this by using Conda and setting up a virtual environment.
	- On mac terminal
		```bash
		$ brew install sox coreutils
		$ pip install -r requirements.txt
    	```
	- On Ubuntu terminal
		```bash
		$ apt-get install sox coreutilss
		$ pip install -r requirements.txt
		```

### Usage
1. Navigate to the 'Korean_FA' directory.
2. Open the 'forced_align.sh' file with any text editor to specify the user path of the Kaldi directory.
	- Change 'kaldi' name variable. (initial setting: kaldi=/home/kaldi)
3. Run the code with the path to the data for forced alignment.

	```bash
	$ bash forced_align.sh (options) (data directory)
	$ bash forced_align.sh -nw ./example/readspeech
 	- Options
	 	1. -h  | --help    : display instruction.
	 	2. -nj | --num-job : Parallel alignment to speed up.
	 	3. -s  | --skip    : Skip alignment for already aligned data.
	 	4. -nw | --no-word : remove word tier.
	 	5. -np | --no-phone: remove phone tier.
	```

4. Textgrid(s) will be saved in the data directory.

## Materials (Data Preparation)
1. **Audio files (.wav)** (sampling rate at 16,000Hz)
	- Please ensure that your audio file(s) are in WAV format ('.wav') and have a sampling rate of 16,000Hz.
	- Korean_FA is designed to work with audio files that have a sampling rate of 16,000Hz.
2. **Text files (.txt)**
	- When naming your transcription text files, please use ordered numbers as suffixes.
		- ex) name01.txt, name02.txt, ...
	- Each text file should contain one complete sentence.
	- **Refrain** from including any punctuation marks such as periods ('.') or commas (',') in the text file.
	- The sentences should be written in the target language.
	- Ensure there are no trailing white spaces or tabs at the end of each line.

## VERSION HISTORY
- v.1.0(08/27/16): Introduced gmm, sgmm_mmi, and dnn-based Korean FA.
- v.1.1(09/06/16): Updated g2p. Added the monophone model.
- v.1.2(10/10/16): Simplified phoneset. Removed the option to choose models like dnn or gmm for forced alignment.
- v.1.3(10/24/16): Introduced the ability to select specific labels in TextGrid. Changed the alignment procedure to align audio files one by one in the directory. This change increased alignment time but improved accuracy. Detailed alignment process information is now available in the log directory, along with more useful command-line information.
- v.1.4(01.14.16): Improved error handling. Log files are now tagged with respect to each wave file name.
- v.1.5(02.08.17): Major changes in the g2p system to make it compatible with the new g2p system. Added a skipping option to skip alignment of audio files with existing TextGrids. Fixed a few minor bugs.
- v.1.5.1(02.26.17): Addressed bug reports, particularly related to time mismatch in the word tier. Fixed the issue.
- v.1.5.2(05.17.17): Made changes to return and exit procedures, resolved option errors, and fixed minor bugs. Added a skip option.
- v.1.5.3(07.10.17): Enabled the alignment of long audio files. Increased information printing on the screen. Resolved a floating error causing time mismatch between the start and end points of each phone segment.
- v.1.5.4(11.14.17): Addressed a floating error in the Kaldi code. This error will be resolved during post-processing, and it's expected that time mismatch errors will no longer occur
- v.1.6(01.18.18): Introduced the num-jb option to split multiple files into subgroups and align multiple files simultaneously, speeding up the alignment process. Made changes to how log histories are printed and adjusted the structure of the main script.
- v.1.6.1(10.28.20):Stabilized the lexicon process. Removed redundant jobs in main_fa.sh and fa_prep_data.sh.
- v1.6.2(01.03.21): Adjusted the audio processing part (sampling rate = 16,000, channel = 1, bit = 16) and changed log variables.
- **v.1.7.0(09.03.23)**: Introduced a web UI available in a Docker image.