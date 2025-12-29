import os
import sys
import tempfile
import time
import platform
import logging
import ctypes

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Helper: determine if running elevated (Windows)
def _is_admin_windows():
    if platform.system() != 'Windows':
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0  # type: ignore[attr-defined]
    except Exception:
        return False

# Helper: attempt to test symlink capability (Windows)
def _can_create_symlink():
    if platform.system() != 'Windows':
        return True
    test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '_symlink_test'))
    target = os.path.join(test_dir, 'target.txt')
    link = os.path.join(test_dir, 'link.txt')
    try:
        os.makedirs(test_dir, exist_ok=True)
        with open(target, 'w', encoding='utf-8') as f:
            f.write('test')
        try:
            os.symlink(target, link)
            return True
        except (OSError, NotImplementedError):
            return False
    finally:
        try:
            if os.path.exists(link):
                os.remove(link)
            if os.path.exists(target):
                os.remove(target)
            if os.path.isdir(test_dir):
                os.rmdir(test_dir)
        except Exception:
            pass

# --- Robust Cache and Environment Setup ---
# Define the project's root directory to store models locally
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(SCRIPT_DIR, 'models')

# Create main cache directories (project-local)
for subdir in ['torch', 'huggingface', 'speechbrain', 'diarizer']:
    os.makedirs(os.path.join(MODEL_DIR, subdir), exist_ok=True)

# Set environment variables for Hugging Face and related libs to use project-local cache
os.environ['HF_HOME'] = os.path.join(MODEL_DIR, 'huggingface')
os.environ['HUGGINGFACE_HUB_CACHE'] = os.path.join(MODEL_DIR, 'huggingface')
os.environ['TORCH_HOME'] = os.path.join(MODEL_DIR, 'torch')
os.environ['SPEECHBRAIN_CACHE_DIR'] = os.path.join(MODEL_DIR, 'speechbrain')

# Disable symlinks and other problematic features, especially critical for Windows
if platform.system() == 'Windows':
    admin = _is_admin_windows()
    symlink_ok = _can_create_symlink()
    if symlink_ok:
        # Allow symlinks for performance; do not force-disable
        logger.info('Windows symlink capability detected (admin=%s). Using normal HuggingFace cache behavior.', admin)
        # Ensure warnings about symlinks are not spammy
        os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')
    else:
        # Fallback: disable symlinks to avoid WinError 1314
        os.environ['HF_HUB_DISABLE_SYMLINKS'] = '1'
        os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
        logger.debug('Symlinks not permitted (admin=%s). Disabled HuggingFace symlinks to avoid privilege errors.', admin)
else:
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS', '1')
    os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')

os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['HF_HUB_OFFLINE'] = '0'

# Set network timeouts
os.environ.setdefault('HF_HUB_ETAG_TIMEOUT', '30')
os.environ.setdefault('HF_HUB_READ_TIMEOUT', '60')
os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '300'

# Configure socket timeout globally
import socket
socket.setdefaulttimeout(60)

# Suppress warnings
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

missing_deps = []
try:
    import torch  # noqa: F401
except Exception as e:  # pragma: no cover
    missing_deps.append(f"torch ({e})")
try:
    from flask import Flask, request, jsonify
except ImportError as e:
    raise RuntimeError("Flask is required to run the backend. Install dependencies with 'pip install -r requirements.txt'.") from e
try:
    from flask_cors import CORS  # noqa: F401
except ImportError:
    missing_deps.append('Flask-Cors')
try:
    from flask_sqlalchemy import SQLAlchemy  # noqa: F401
except ImportError:
    missing_deps.append('Flask-SQLAlchemy')
try:
    from faster_whisper import WhisperModel  # noqa: F401
except Exception as e:
    missing_deps.append(f"faster-whisper ({e})")
try:
    from pydub import AudioSegment  # noqa: F401
except Exception as e:
    missing_deps.append(f"pydub ({e})")
try:
    from transformers import pipeline  # noqa: F401
except Exception as e:
    missing_deps.append(f"transformers ({e})")
try:
    from simple_diarizer.diarizer import Diarizer  # noqa: F401
except Exception as e:
    missing_deps.append(f"simple-diarizer ({e})")
import shutil
import inspect

if missing_deps:
    logger.warning("Some optional/required dependencies not imported: %s", ", ".join(missing_deps))
warnings.filterwarnings("ignore", category=DeprecationWarning)

def clean_problematic_cache():
    """Clean problematic cache files that may cause symlink issues on Windows."""
    if platform.system() != "Windows":
        return
    
    try:
        # Clean user's HuggingFace cache for speechbrain model
        user_cache_dir = os.path.join(
            os.path.expanduser('~'), 
            '.cache', 
            'huggingface', 
            'hub', 
            'models--speechbrain--spkrec-xvect-voxceleb'
        )
        
        if os.path.exists(user_cache_dir):
            logger.info(f"Cleaning problematic cache directory: {user_cache_dir}")
            shutil.rmtree(user_cache_dir, ignore_errors=True)
            
        # Clean project cache as well
        project_cache_dir = os.path.join(MODEL_DIR, 'huggingface', 'models--speechbrain--spkrec-xvect-voxceleb')
        if os.path.exists(project_cache_dir):
            logger.info(f"Cleaning project cache directory: {project_cache_dir}")
            shutil.rmtree(project_cache_dir, ignore_errors=True)
            
        logger.info("Cache cleaning completed. Please restart the application.")
        
    except Exception as e:
        logger.warning(f"Cache cleaning failed (non-fatal): {e}")


# --- CONFIGURE FFmpeg/AudioSegment ---
FFMPEG_PATH = r"C:\ffmpeg-master-latest-win64-gpl-shared\bin"
FFMPEG_EXE = os.path.join(FFMPEG_PATH, 'ffmpeg.exe')
FFPROBE_EXE = os.path.join(FFMPEG_PATH, 'ffprobe.exe')

def verify_ffmpeg():
    if not os.path.exists(FFMPEG_PATH):
        raise RuntimeError(f"FFmpeg directory not found at: {FFMPEG_PATH}")
    if not os.path.exists(FFMPEG_EXE):
        raise RuntimeError(f"ffmpeg.exe not found at: {FFMPEG_EXE}")
    if not os.path.exists(FFPROBE_EXE):
        raise RuntimeError(f"ffprobe.exe not found at: {FFPROBE_EXE}")
    if FFMPEG_PATH not in os.environ['PATH']:
        os.environ['PATH'] = FFMPEG_PATH + os.pathsep + os.environ['PATH']
    AudioSegment.converter = FFMPEG_EXE
    AudioSegment.ffprobe = FFPROBE_EXE
    print("✓ FFmpeg configured successfully.")

try:
    verify_ffmpeg()
except Exception as e:
    print(f"ERROR: FFmpeg configuration failed: {str(e)}", file=sys.stderr)
    sys.exit(1)

# --- Configuration for Low-End Efficiency ---
WHISPER_MODEL_SIZE = "base.en"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
START_TIME = time.time()

# --- Flask App and Database Initialization ---
app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(SCRIPT_DIR, 'transcriptions.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Model (Modified: Translation removed) ---
class TranscriptionJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    transcript = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    # Translation column removed
    language = db.Column(db.String(10), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'language': self.language,
            'transcript': self.transcript,
            'summary': self.summary,
            'created_at': self.created_at.isoformat()
        }

# --- Model Loading ---
WHISPER_MODEL = None
DIARIZER_MODEL = None

def timeout_handler(signum, frame):
    """Timeout handler for download operations."""
    raise TimeoutError("Download operation timed out. Check your internet connection.")

def download_with_timeout(repo_id, local_dir, timeout_seconds=300, offline_fallback=True, **kwargs):
    """Wrapper for snapshot_download with timeout protection and offline fallback."""
    from huggingface_hub import snapshot_download
    import signal
    
    logger.info(f"Downloading {repo_id} with {timeout_seconds}s timeout...")
    
    if os.path.exists(local_dir) and len(os.listdir(local_dir)) > 0:
        logger.info(f"✓ {repo_id} already exists locally at {local_dir}. Skipping download.")
        return local_dir
    
    old_handler = None
    if platform.system() != 'Windows':
        try:
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout_seconds)
        except (AttributeError, ValueError):
            pass
    
    try:
        return snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            **kwargs
        )
    except TimeoutError as e:
        logger.error(f"Download timeout for {repo_id}: {e}")
        if offline_fallback and os.path.exists(local_dir):
            logger.warning(f"Attempting offline fallback for {repo_id}...")
            if len(os.listdir(local_dir)) > 0:
                logger.info(f"Using partially downloaded files from {local_dir}")
                return local_dir
        raise
    except Exception as e:
        logger.error(f"Download failed for {repo_id}: {e}")
        if offline_fallback and os.path.exists(local_dir) and len(os.listdir(local_dir)) > 0:
            logger.warning(f"Download failed but partial files exist. Using offline fallback...")
            return local_dir
        raise
    finally:
        if platform.system() != 'Windows' and old_handler is not None:
            try:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            except (AttributeError, ValueError):
                pass

def load_with_retries(load_func, model_name, max_attempts=3, delay=2):
    """Generic retry wrapper for model loading with Windows-specific error handling."""
    last_exception = None
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"[Attempt {attempt}/{max_attempts}] Loading {model_name}...")
            result = load_func()
            logger.info(f"✓ {model_name} loaded successfully.")
            return result
        except TimeoutError as e:
            last_exception = e
            logger.warning(f"Timeout while loading {model_name} (attempt {attempt}): {e}")
            logger.warning("This may indicate network connectivity issues or slow HuggingFace hub.")
            if attempt < max_attempts:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
        except OSError as e:
            last_exception = e
            if hasattr(e, 'winerror') and e.winerror == 1314:
                if attempt == 1:
                    logger.warning("WinError 1314 (no symlink privilege). Switching to copy-only fallback.")
                
                if attempt == 1 and platform.system() == "Windows":
                    logger.info("Attempting automatic cache cleanup...")
                    clean_problematic_cache()
            else:
                logger.warning(f"Error loading {model_name} (attempt {attempt}): {e}")
            
            if attempt < max_attempts:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
        except Exception as e:
            last_exception = e
            logger.warning(f"Error loading {model_name} (attempt {attempt}): {e}")
            if attempt < max_attempts:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
    
    logger.error(f"FATAL: {model_name} failed after {max_attempts} attempts.")
    
    if (platform.system() == "Windows" and 
        isinstance(last_exception, OSError) and 
        hasattr(last_exception, 'winerror') and 
        last_exception.winerror == 1314):
        logger.error("Windows symlink privilege error detected.")
    
    raise last_exception

def load_whisper_model():
    """Load Whisper model with proper configuration."""
    return WhisperModel(
        WHISPER_MODEL_SIZE, 
        device=DEVICE, 
        compute_type=COMPUTE_TYPE, 
        download_root=os.path.join(MODEL_DIR, 'faster-whisper'), 
        local_files_only=False
    )

def load_diarizer_model():
    """Load Diarizer model with Windows symlink workaround."""
    from huggingface_hub import snapshot_download
    from speechbrain.inference.classifiers import EncoderClassifier
    import logging as _logging

    for noisy in ["speechbrain", "huggingface_hub", "transformers"]:
        try:
            _logging.getLogger(noisy).setLevel(_logging.WARNING)
        except Exception:
            pass
    
    if platform.system() == "Windows":
        try:
            import types as _types
            def _safe_symlink(src, dst, *a, **kw):
                try:
                    if os.path.isdir(src):
                        if not os.path.exists(dst):
                            shutil.copytree(src, dst)
                    else:
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        if not os.path.exists(dst):
                            shutil.copy2(src, dst)
                except Exception as copy_e:  # noqa: F841
                    pass
            if getattr(os, 'symlink', None):
                os.symlink = _safe_symlink  # type: ignore
        except Exception:
            pass
    
    spkrec_dir = os.path.join(MODEL_DIR, 'speechbrain', 'spkrec-xvect-voxceleb')
    os.makedirs(spkrec_dir, exist_ok=True)

    logger.info("Pre-caching speechbrain speaker recognition model (copy-only mode)...")
    
    download_with_timeout(
        repo_id="speechbrain/spkrec-xvect-voxceleb",
        local_dir=spkrec_dir,
        local_dir_use_symlinks=False,
        cache_dir=os.path.join(MODEL_DIR, 'huggingface'),
        repo_type='model',
        force_download=False,
        timeout_seconds=300
    )

    if platform.system() == "Windows":
        try:
            user_hub_snapshots = os.path.join(
                os.path.expanduser('~'), 
                '.cache', 
                'huggingface', 
                'hub', 
                'models--speechbrain--spkrec-xvect-voxceleb', 
                'snapshots'
            )
            if os.path.exists(user_hub_snapshots):
                snapshots = [
                    os.path.join(user_hub_snapshots, d) 
                    for d in os.listdir(user_hub_snapshots) 
                    if os.path.isdir(os.path.join(user_hub_snapshots, d))
                ]
                if snapshots:
                    snapshots.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                    src_snapshot = snapshots[0]
                    
                    for root, _, files in os.walk(src_snapshot):
                        for f in files:
                            src_file = os.path.join(root, f)
                            rel = os.path.relpath(src_file, src_snapshot)
                            dst_file = os.path.join(spkrec_dir, rel)
                            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
                            try:
                                if not os.path.exists(dst_file):
                                    shutil.copy2(src_file, dst_file)
                            except Exception as copy_error:
                                logger.debug(f"Non-fatal copy error: {copy_error}")
        except Exception as e:
            logger.debug(f"Windows workaround failed (non-fatal): {e}")

    EncoderClassifier.from_hparams(
        source=spkrec_dir,
        savedir=spkrec_dir,
        run_opts={"device": DEVICE}
    )
    logger.info("✓ Speechbrain model cached.")
    
    diarizer_instance = None
    try:
        init_sig = inspect.signature(Diarizer.__init__)
        if 'device' in init_sig.parameters:
            diarizer_instance = Diarizer(device=DEVICE)
        else:
            diarizer_instance = Diarizer()
        logger.info("✓ Diarizer model instantiated.")
    except TypeError as te:
        if 'unexpected keyword argument' in str(te) and diarizer_instance is None:
            try:
                diarizer_instance = Diarizer()
                logger.info("✓ Diarizer model instantiated (without device kw).")
            except Exception as inner:
                raise inner
        else:
            raise te
    except Exception as e:
        logger.warning(f"Falling back to SimpleFallbackDiarizer due to error: {e}")
        class SimpleFallbackDiarizer:
            def diarize(self, wav_path):
                try:
                    from pydub import AudioSegment as _AS
                    ms = len(_AS.from_file(wav_path))
                    seconds = ms / 1000.0
                except Exception:
                    seconds = 0.0
                return [{"start": 0.0, "end": seconds, "label": "SPEAKER_00"}]
        diarizer_instance = SimpleFallbackDiarizer()
        logger.info("Using SimpleFallbackDiarizer (single-speaker assumption).")
    return diarizer_instance

def load_models():
    """Load all required models with robust error handling."""
    global WHISPER_MODEL, DIARIZER_MODEL
    
    try:
        WHISPER_MODEL = load_with_retries(load_whisper_model, "Whisper model")
        DIARIZER_MODEL = load_with_retries(load_diarizer_model, "Diarizer model")
        return True
    except Exception as e:
        logger.error(f"Failed to load required models: {e}")
        return False

# --- Helper Functions and API Endpoints ---

def simple_sentence_tokenize(text):
    endings = ['. ', '! ', '? ', '.\n', '!\n', '?\n']
    abbreviations = {'Mr.': 'Mr_', 'Mrs.': 'Mrs_', 'Ms.': 'Ms_', 'Dr.': 'Dr_'}
    working_text = text
    for abbr, repl in abbreviations.items(): working_text = working_text.replace(abbr, repl)
    for ending in endings: working_text = working_text.replace(ending, '\n')
    sentences = [s.strip() for s in working_text.split('\n') if s.strip()]
    for abbr, repl in abbreviations.items(): sentences = [s.replace(repl, abbr) for s in sentences]
    return sentences

def summarize_text_extractive(text, style="professional"):
    if not text or len(text.split()) < 20: return text
    
    from heapq import nlargest
    
    style_config = {
        'short':        {'ratio': 0.15, 'min_sent': 1},
        'professional': {'ratio': 0.25, 'min_sent': 2},
        'long':         {'ratio': 0.40, 'min_sent': 5},
        'bullet_points':{'ratio': 0.20, 'min_sent': 3},
        'report':       {'ratio': 0.50, 'min_sent': 5},
        'abstract':     {'ratio': 0.10, 'min_sent': 1},
        'action_items': {'ratio': 0.15, 'min_sent': 2}
    }
    
    config = style_config.get(style.lower(), style_config['professional'])
    ratio = config['ratio']
    
    sentences = simple_sentence_tokenize(text)
    words = [word for word in text.lower().split() if word.isalnum()]
    word_frequencies = {word: words.count(word) for word in set(words)}
    
    sentence_scores = {}
    for sentence in sentences:
        for word in sentence.lower().split():
            if word in word_frequencies:
                if len(sentence.split()) < 30:
                    if sentence not in sentence_scores: sentence_scores[sentence] = 0
                    sentence_scores[sentence] += word_frequencies[word]
        if sentence in sentence_scores:
            sentence_scores[sentence] = sentence_scores[sentence] / (len(sentence.split()) + 1)

    select_length = max(config['min_sent'], int(len(sentences) * ratio))
    summary_sentences = nlargest(select_length, sentence_scores, key=sentence_scores.get)
    
    if style.lower() == "bullet_points" or style.lower() == "action_items":
        summary = "\n• " + "\n• ".join(summary_sentences)
    elif style.lower() == "report":
        summary = "--- REPORT ---\n\n" + "\n\n".join(summary_sentences)
    else:
        summary = " ".join(summary_sentences)
        
    return summary

def format_timestamp(seconds):
    h = int(seconds // 3600); m = int((seconds % 3600) // 60); s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "uptime": int(time.time() - START_TIME),
        "models_loaded": { "whisper": WHISPER_MODEL is not None, "diarization": DIARIZER_MODEL is not None, "summarizer": True }
    })

@app.route('/deps', methods=['GET'])
def deps_check():
    return jsonify({
        "missing": missing_deps,
        "python": sys.version,
        "platform": platform.platform(),
    })

@app.route('/transcribe', methods=['POST'])
def transcribe_audio_api():
    if 'audio' not in request.files:
        return jsonify({"error": "No audio file(s) provided"}), 400
    audio_files = request.files.getlist('audio')
    
    if WHISPER_MODEL is None or DIARIZER_MODEL is None:
        return jsonify({"error": "A required model is not loaded"}), 503

    results = []
    for audio_file in audio_files:
        unique_dir = tempfile.mkdtemp()
        try:
            file_ext = os.path.splitext(audio_file.filename)[1].lower()
            temp_path = os.path.join(unique_dir, f"uploaded_audio{file_ext}")
            audio_file.save(temp_path)

            audio = AudioSegment.from_file(temp_path).set_channels(1).set_frame_rate(16000)
            wav_path = os.path.join(unique_dir, "processed_audio.wav")
            audio.export(wav_path, format="wav", parameters=["-acodec", "pcm_s16le"])

            whisper_segments, info = WHISPER_MODEL.transcribe(wav_path, beam_size=5, word_timestamps=True)
            diarization_segments = DIARIZER_MODEL.diarize(wav_path)
            
            word_list = []
            for seg in whisper_segments:
                for word in getattr(seg, 'words', []):
                    word_list.append({'word': word.word, 'start': word.start, 'end': word.end})

            transcript_segments = []
            speaker_map = {}
            
            for dia_segment in diarization_segments:
                start_time = dia_segment['start']
                end_time = dia_segment['end']
                speaker_label = dia_segment['label']

                if speaker_label not in speaker_map:
                    speaker_map[speaker_label] = f"Person {len(speaker_map) + 1}"
                speaker_name = speaker_map[speaker_label]
                
                segment_words = [word['word'] for word in word_list if start_time <= (word['start'] + word['end']) / 2 <= end_time]
                
                if segment_words:
                    turn_text = " ".join(segment_words)
                    transcript_segments.append({ "speaker": speaker_name, "time": format_timestamp(start_time), "text": turn_text.strip() })

            if not transcript_segments:
                return jsonify({"error": "Could not transcribe or diarize speech."}), 400

            full_text = "\n".join([f"{s['speaker']}: {s['text']}" for s in transcript_segments])
            new_job = TranscriptionJob(filename=audio_file.filename, language=getattr(info, 'language', 'en'), transcript=full_text)
            db.session.add(new_job)
            db.session.commit()
            
            results.append({ "job_id": new_job.id, "filename": audio_file.filename, "language": new_job.language, "transcript": transcript_segments })

        except Exception as e:
            print(f"Error during transcription: {str(e)}", file=sys.stderr)
            results.append({"filename": audio_file.filename, "error": f"Failed to process file: {str(e)}"})
        finally:
            if os.path.exists(unique_dir):
                shutil.rmtree(unique_dir)
    return jsonify({"results": results})

@app.route('/summarize', methods=['POST'])
def summarize_text_api():
    data = request.get_json()
    if not data or 'text' not in data or 'style' not in data:
        return jsonify({"error": "Missing text or style in request"}), 400
    
    text = data['text']
    style = data.get('style', 'professional')
    
    style_mapping = {
        'bullets': 'bullet_points',
        'professional': 'professional',
        'simple': 'short',
        'report': 'report',
        'abstract': 'abstract',
        'actions': 'action_items'
    }
    backend_style = style_mapping.get(style, style)
    
    summary = summarize_text_extractive(text, style=backend_style)
    
    if 'job_id' in data:
        job = TranscriptionJob.query.get(data['job_id'])
        if job:
            job.summary = summary
            db.session.commit()
            return jsonify({"summary": summary, "message": f"Summary saved to job {job.id}"})
    return jsonify({"summary": summary})

@app.route('/history', methods=['GET'])
def get_history():
    jobs = TranscriptionJob.query.order_by(TranscriptionJob.created_at.desc()).all()
    return jsonify([job.to_dict() for job in jobs])

@app.route('/history/<int:job_id>', methods=['GET'])
def get_job_by_id(job_id):
    job = TranscriptionJob.query.get(job_id)
    if job: return jsonify(job.to_dict())
    return jsonify({"error": "Job not found"}), 404

if __name__ == '__main__':
    try:
        # Initialize database
        with app.app_context():
            db.create_all()
        
        logger.info("Initializing models...")
        if not load_models():
            logger.error("FATAL ERROR: Failed to load required models. The application cannot start.")
            logger.error("Please check the error messages above for specific solutions.")
            sys.exit(1)
        
        logger.info("✓ All models loaded successfully!")
        logger.info("Starting Flask server at http://127.0.0.1:5000")
        app.run(host='127.0.0.1', port=5000, debug=False)
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal application error: {e}")
        sys.exit(1)