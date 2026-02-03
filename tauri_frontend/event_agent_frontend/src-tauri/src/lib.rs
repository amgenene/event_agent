// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/
use std::sync::{Arc, Mutex};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use tauri::{Emitter, Manager, State, Window};

struct CpalStreamWrapper(cpal::Stream);

// cpal::Stream on macOS is not Send/Sync by default, but we need it for Tauri State.
// Since we protect it with a Mutex, it's generally safe to move effectively.
unsafe impl Send for CpalStreamWrapper {}
unsafe impl Sync for CpalStreamWrapper {}

struct MonitoringState {
    stream: Arc<Mutex<Option<CpalStreamWrapper>>>,
}

#[derive(serde::Serialize, Clone)]
struct AudioLevel {
    rms: f32,
    peak: f32,
}

#[tauri::command]
fn start_monitor(state: State<MonitoringState>, window: Window) -> Result<(), String> {
    println!("Starting audio monitor");
    let mut stream_guard = state.stream.lock().map_err(|e| e.to_string())?;

    if stream_guard.is_some() {
        println!("Monitor already running");
        return Ok(());
    }

    let host = cpal::default_host();
    let device = host
        .default_input_device()
        .ok_or("No input device available")?;

    println!("Using input device: {}", device.name().unwrap_or_default());

    let config: cpal::StreamConfig = device.default_input_config().map_err(|e| e.to_string())?.into();

    let window_arc = Arc::new(window);
    
    // We want to process audio and emit events at a reasonable rate (e.g. 30-60Hz)
    // Audio callbacks happen very frequently, so we accumulate samples
    // Actually, for a simple waveform, calculating RMS per buffer is usually fine
    
    let err_fn = move |err| {
        eprintln!("an error occurred on stream: {}", err);
    };

    let stream = device.build_input_stream(
        &config,
        move |data: &[f32], _: &_| {
            // Calculate RMS (Root Mean Square) for volume
            let mut sum_squares = 0.0;
            let mut peak = 0.0;
            
            for &sample in data {
                let abs_sample = sample.abs();
                if abs_sample > peak {
                    peak = abs_sample;
                }
                sum_squares += sample * sample;
            }
            
            let rms = (sum_squares / data.len() as f32).sqrt();
            
            // Emit if significant or throttled? 
            // Just emitting every buffer is simplest, though might be high frequency.
            // A buffer of 1024 samples at 44.1kHz is ~23ms (43Hz), which is perfect for UI.
            
            let _ = window_arc.emit("audio-level", AudioLevel { rms, peak });
        },
        err_fn,
        None
    ).map_err(|e| e.to_string())?;

    stream.play().map_err(|e| e.to_string())?;
    
    *stream_guard = Some(CpalStreamWrapper(stream));
    println!("Audio monitor started successfully");
    Ok(())
}

#[tauri::command]
fn stop_monitor(state: State<MonitoringState>) -> Result<(), String> {
    println!("Stopping audio monitor");
    let mut stream_guard = state.stream.lock().map_err(|e| e.to_string())?;
    // Dropping the stream stops it
    *stream_guard = None;
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
        .manage(MonitoringState {
            stream: Arc::new(Mutex::new(None)),
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
        .plugin(tauri_plugin_mic_recorder::init())
        .setup(move |app| {
            // register the global shortcut so the handler receives events
            app.handle()
                .global_shortcut()
                .register(show_shortcut.clone())
                .expect("failed to register global shortcut");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![greet, start_monitor, stop_monitor])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
