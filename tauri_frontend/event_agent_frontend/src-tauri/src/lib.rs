// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::SampleFormat;
use tauri::{AppHandle, Emitter, Manager, State, Window};
use std::fs;
use std::path::PathBuf;

struct CpalStreamWrapper(cpal::Stream);

// cpal::Stream on macOS is not Send/Sync by default, but we need it for Tauri State.
// Since we protect it with a Mutex, it's generally safe to move effectively.
unsafe impl Send for CpalStreamWrapper {}
unsafe impl Sync for CpalStreamWrapper {}

struct RecordingState {
    stream: Arc<Mutex<Option<CpalStreamWrapper>>>,
    samples: Arc<Mutex<Vec<i16>>>,
    sample_rate: Arc<Mutex<u32>>,
}

#[derive(serde::Serialize, Clone)]
struct AudioLevel {
    rms: f32,
    peak: f32,
}

#[derive(serde::Serialize, serde::Deserialize, Clone)]
struct LocationSettings {
    location: String,
    country: Option<String>,
}

fn log_stream_error(err: cpal::StreamError) {
    eprintln!("an error occurred on stream: {}", err);
}

fn process_input_f32(
    data: &[f32],
    channels: usize,
    samples: &Arc<Mutex<Vec<i16>>>,
    window: &Window,
) {
    if data.is_empty() || channels == 0 {
        return;
    }

    let mut sum_squares = 0.0f32;
    let mut peak = 0.0f32;
    let mut mono_samples = Vec::with_capacity(data.len() / channels);

    for frame in data.chunks(channels) {
        if frame.len() < channels {
            break;
        }
        let mut acc = 0.0f32;
        for &sample in frame {
            let clamped = sample.clamp(-1.0, 1.0);
            let abs_sample = clamped.abs();
            if abs_sample > peak {
                peak = abs_sample;
            }
            sum_squares += clamped * clamped;
            acc += clamped;
        }
        let mono = acc / channels as f32;
        let mono_i16 = (mono.clamp(-1.0, 1.0) * i16::MAX as f32) as i16;
        mono_samples.push(mono_i16);
    }

    let rms = (sum_squares / data.len() as f32).sqrt();

    if let Ok(mut guard) = samples.lock() {
        guard.extend(mono_samples);
    }

    let _ = window.emit("audio-level", AudioLevel { rms, peak });
}

fn process_input_i16(
    data: &[i16],
    channels: usize,
    samples: &Arc<Mutex<Vec<i16>>>,
    window: &Window,
) {
    if data.is_empty() || channels == 0 {
        return;
    }

    let mut sum_squares = 0.0f32;
    let mut peak = 0.0f32;
    let mut mono_samples = Vec::with_capacity(data.len() / channels);

    for frame in data.chunks(channels) {
        if frame.len() < channels {
            break;
        }
        let mut acc = 0.0f32;
        for &sample in frame {
            let normalized = sample as f32 / i16::MAX as f32;
            let abs_sample = normalized.abs();
            if abs_sample > peak {
                peak = abs_sample;
            }
            sum_squares += normalized * normalized;
            acc += normalized;
        }
        let mono = acc / channels as f32;
        let mono_i16 = (mono.clamp(-1.0, 1.0) * i16::MAX as f32) as i16;
        mono_samples.push(mono_i16);
    }

    let rms = (sum_squares / data.len() as f32).sqrt();

    if let Ok(mut guard) = samples.lock() {
        guard.extend(mono_samples);
    }

    let _ = window.emit("audio-level", AudioLevel { rms, peak });
}

fn process_input_u16(
    data: &[u16],
    channels: usize,
    samples: &Arc<Mutex<Vec<i16>>>,
    window: &Window,
) {
    if data.is_empty() || channels == 0 {
        return;
    }

    let mut sum_squares = 0.0f32;
    let mut peak = 0.0f32;
    let mut mono_samples = Vec::with_capacity(data.len() / channels);

    for frame in data.chunks(channels) {
        if frame.len() < channels {
            break;
        }
        let mut acc = 0.0f32;
        for &sample in frame {
            let normalized = (sample as f32 / u16::MAX as f32) * 2.0 - 1.0;
            let abs_sample = normalized.abs();
            if abs_sample > peak {
                peak = abs_sample;
            }
            sum_squares += normalized * normalized;
            acc += normalized;
        }
        let mono = acc / channels as f32;
        let mono_i16 = (mono.clamp(-1.0, 1.0) * i16::MAX as f32) as i16;
        mono_samples.push(mono_i16);
    }

    let rms = (sum_squares / data.len() as f32).sqrt();

    if let Ok(mut guard) = samples.lock() {
        guard.extend(mono_samples);
    }

    let _ = window.emit("audio-level", AudioLevel { rms, peak });
}

#[tauri::command]
fn start_recording(state: State<RecordingState>, window: Window) -> Result<(), String> {
    println!("Starting recording");
    let mut stream_guard = state.stream.lock().map_err(|e| e.to_string())?;

    if stream_guard.is_some() {
        println!("Recording already running");
        return Ok(());
    }

    let host = cpal::default_host();
    let device = host
        .default_input_device()
        .ok_or("No input device available")?;

    println!("Using input device: {}", device.name().unwrap_or_default());

    let supported_config = device.default_input_config().map_err(|e| e.to_string())?;
    let sample_format = supported_config.sample_format();
    let config: cpal::StreamConfig = supported_config.into();
    let channels = config.channels as usize;

    {
        let mut rate_guard = state.sample_rate.lock().map_err(|e| e.to_string())?;
        *rate_guard = config.sample_rate.0;
        let mut samples_guard = state.samples.lock().map_err(|e| e.to_string())?;
        samples_guard.clear();
    }

    let samples = state.samples.clone();
    let window = Arc::new(window);

    let stream = match sample_format {
        SampleFormat::F32 => {
            let samples = samples.clone();
            let window = window.clone();
            device.build_input_stream(
                &config,
                move |data: &[f32], _: &_| {
                    process_input_f32(data, channels, &samples, &window);
                },
                log_stream_error,
                None,
            )
        }
        SampleFormat::I16 => {
            let samples = samples.clone();
            let window = window.clone();
            device.build_input_stream(
                &config,
                move |data: &[i16], _: &_| {
                    process_input_i16(data, channels, &samples, &window);
                },
                log_stream_error,
                None,
            )
        }
        SampleFormat::U16 => {
            let samples = samples.clone();
            let window = window.clone();
            device.build_input_stream(
                &config,
                move |data: &[u16], _: &_| {
                    process_input_u16(data, channels, &samples, &window);
                },
                log_stream_error,
                None,
            )
        }
        _ => return Err("Unsupported sample format".to_string()),
    }.map_err(|e| e.to_string())?;

    stream.play().map_err(|e| e.to_string())?;

    *stream_guard = Some(CpalStreamWrapper(stream));
    println!("Recording started successfully");
    Ok(())
}

#[tauri::command]
fn stop_recording(state: State<RecordingState>) -> Result<String, String> {
    println!("Stopping recording");
    let mut stream_guard = state.stream.lock().map_err(|e| e.to_string())?;
    if stream_guard.is_none() {
        return Err("Recording is not running".to_string());
    }
    *stream_guard = None;
    drop(stream_guard);

    let sample_rate = {
        let guard = state.sample_rate.lock().map_err(|e| e.to_string())?;
        if *guard == 0 { 44_100 } else { *guard }
    };

    let samples = {
        let mut guard = state.samples.lock().map_err(|e| e.to_string())?;
        let data = guard.clone();
        guard.clear();
        data
    };

    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| e.to_string())?
        .as_millis();
    let file_path = std::env::temp_dir().join(format!("event_searcher_recording_{timestamp}.wav"));

    let spec = hound::WavSpec {
        channels: 1,
        sample_rate,
        bits_per_sample: 16,
        sample_format: hound::SampleFormat::Int,
    };

    let mut writer = hound::WavWriter::create(&file_path, spec).map_err(|e| e.to_string())?;
    for sample in samples {
        writer.write_sample(sample).map_err(|e| e.to_string())?;
    }
    writer.finalize().map_err(|e| e.to_string())?;

    Ok(file_path.to_string_lossy().to_string())
}

#[tauri::command]
fn cancel_recording(state: State<RecordingState>) -> Result<(), String> {
    println!("Canceling recording");
    let mut stream_guard = state.stream.lock().map_err(|e| e.to_string())?;
    *stream_guard = None;

    let mut samples_guard = state.samples.lock().map_err(|e| e.to_string())?;
    samples_guard.clear();

    Ok(())
}

fn location_file_path(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_config_dir()
        .map_err(|e| e.to_string())?;
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir.join("location.json"))
}

#[tauri::command]
fn get_saved_location(app: AppHandle) -> Result<Option<LocationSettings>, String> {
    let path = location_file_path(&app)?;
    if !path.exists() {
        return Ok(None);
    }
    let contents = fs::read_to_string(path).map_err(|e| e.to_string())?;
    let settings: LocationSettings = serde_json::from_str(&contents).map_err(|e| e.to_string())?;
    Ok(Some(settings))
}

#[tauri::command]
fn set_saved_location(app: AppHandle, location: LocationSettings) -> Result<(), String> {
    let path = location_file_path(&app)?;
    let data = serde_json::to_string_pretty(&location).map_err(|e| e.to_string())?;
    fs::write(path, data).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

    // Register Alt+E as the global shortcut (SuperWhisper-like behavior)
    let show_shortcut = Shortcut::new(Some(Modifiers::ALT), Code::KeyE);

    tauri::Builder::default()
        .manage(RecordingState {
            stream: Arc::new(Mutex::new(None)),
            samples: Arc::new(Mutex::new(Vec::new())),
            sample_rate: Arc::new(Mutex::new(0)),
        })
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(move |app, _shortcut, event| {
                    if event.state() == ShortcutState::Pressed {
                        if let Some(win) = app.get_webview_window("main") {
                            if let Err(e) = win.show() {
                                eprintln!("failed to show window: {:?}", e);
                            }
                            if let Err(e) = win.set_focus() {
                                eprintln!("failed to focus window: {:?}", e);
                            }
                            // Emit event to frontend to start recording
                            if let Err(e) = win.emit("start-recording", ()) {
                                eprintln!("failed to emit start-recording: {:?}", e);
                            }
                        }
                    }
                })
                .build(),
        )
        .plugin(tauri_plugin_opener::init())
        .setup(move |app| {
            // register the global shortcut so the handler receives events
            app.handle()
                .global_shortcut()
                .register(show_shortcut.clone())
                .expect("failed to register global shortcut");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            greet,
            start_recording,
            stop_recording,
            cancel_recording,
            get_saved_location,
            set_saved_location
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
