use std::{
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::{Duration, Instant},
};

use device_query::{DeviceQuery, DeviceState, Keycode};
use enigo::{Enigo, Key as EnigoKey, KeyboardControllable, MouseButton, MouseControllable};
use glium::Surface;
use imgui::{Condition, Context, FontConfig, FontSource, StyleColor, Ui};
use imgui_glium_renderer::Renderer;
use imgui_winit_support::{HiDpiMode, WinitPlatform};
use winit::{event::Event, event::WindowEvent, event_loop::EventLoopBuilder};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum BindKey {
    F1,
    F2,
    F3,
    F4,
    F5,
    F6,
    F7,
    F8,
    F9,
    F10,
    F11,
    F12,
    Q,
    E,
    R,
    T,
    F,
    G,
    V,
    B,
    C,
    X,
    Z,
    MouseLeft,
    MouseRight,
    MouseMiddle,
}

impl BindKey {
    const ALL: [BindKey; 26] = [
        BindKey::F1,
        BindKey::F2,
        BindKey::F3,
        BindKey::F4,
        BindKey::F5,
        BindKey::F6,
        BindKey::F7,
        BindKey::F8,
        BindKey::F9,
        BindKey::F10,
        BindKey::F11,
        BindKey::F12,
        BindKey::Q,
        BindKey::E,
        BindKey::R,
        BindKey::T,
        BindKey::F,
        BindKey::G,
        BindKey::V,
        BindKey::B,
        BindKey::C,
        BindKey::X,
        BindKey::Z,
        BindKey::MouseLeft,
        BindKey::MouseRight,
        BindKey::MouseMiddle,
    ];

    fn as_str(self) -> &'static str {
        match self {
            BindKey::F1 => "F1",
            BindKey::F2 => "F2",
            BindKey::F3 => "F3",
            BindKey::F4 => "F4",
            BindKey::F5 => "F5",
            BindKey::F6 => "F6",
            BindKey::F7 => "F7",
            BindKey::F8 => "F8",
            BindKey::F9 => "F9",
            BindKey::F10 => "F10",
            BindKey::F11 => "F11",
            BindKey::F12 => "F12",
            BindKey::Q => "Q",
            BindKey::E => "E",
            BindKey::R => "R",
            BindKey::T => "T",
            BindKey::F => "F",
            BindKey::G => "G",
            BindKey::V => "V",
            BindKey::B => "B",
            BindKey::C => "C",
            BindKey::X => "X",
            BindKey::Z => "Z",
            BindKey::MouseLeft => "MouseLeft",
            BindKey::MouseRight => "MouseRight",
            BindKey::MouseMiddle => "MouseMiddle",
        }
    }

    fn to_keycode(self) -> Option<Keycode> {
        match self {
            BindKey::F1 => Some(Keycode::F1),
            BindKey::F2 => Some(Keycode::F2),
            BindKey::F3 => Some(Keycode::F3),
            BindKey::F4 => Some(Keycode::F4),
            BindKey::F5 => Some(Keycode::F5),
            BindKey::F6 => Some(Keycode::F6),
            BindKey::F7 => Some(Keycode::F7),
            BindKey::F8 => Some(Keycode::F8),
            BindKey::F9 => Some(Keycode::F9),
            BindKey::F10 => Some(Keycode::F10),
            BindKey::F11 => Some(Keycode::F11),
            BindKey::F12 => Some(Keycode::F12),
            BindKey::Q => Some(Keycode::Q),
            BindKey::E => Some(Keycode::E),
            BindKey::R => Some(Keycode::R),
            BindKey::T => Some(Keycode::T),
            BindKey::F => Some(Keycode::F),
            BindKey::G => Some(Keycode::G),
            BindKey::V => Some(Keycode::V),
            BindKey::B => Some(Keycode::B),
            BindKey::C => Some(Keycode::C),
            BindKey::X => Some(Keycode::X),
            BindKey::Z => Some(Keycode::Z),
            _ => None,
        }
    }

    fn to_enigo_key(self) -> Option<EnigoKey> {
        match self {
            BindKey::F1 => Some(EnigoKey::F1),
            BindKey::F2 => Some(EnigoKey::F2),
            BindKey::F3 => Some(EnigoKey::F3),
            BindKey::F4 => Some(EnigoKey::F4),
            BindKey::F5 => Some(EnigoKey::F5),
            BindKey::F6 => Some(EnigoKey::F6),
            BindKey::F7 => Some(EnigoKey::F7),
            BindKey::F8 => Some(EnigoKey::F8),
            BindKey::F9 => Some(EnigoKey::F9),
            BindKey::F10 => Some(EnigoKey::F10),
            BindKey::F11 => Some(EnigoKey::F11),
            BindKey::F12 => Some(EnigoKey::F12),
            BindKey::Q => Some(EnigoKey::Layout('q')),
            BindKey::E => Some(EnigoKey::Layout('e')),
            BindKey::R => Some(EnigoKey::Layout('r')),
            BindKey::T => Some(EnigoKey::Layout('t')),
            BindKey::F => Some(EnigoKey::Layout('f')),
            BindKey::G => Some(EnigoKey::Layout('g')),
            BindKey::V => Some(EnigoKey::Layout('v')),
            BindKey::B => Some(EnigoKey::Layout('b')),
            BindKey::C => Some(EnigoKey::Layout('c')),
            BindKey::X => Some(EnigoKey::Layout('x')),
            BindKey::Z => Some(EnigoKey::Layout('z')),
            _ => None,
        }
    }

    fn to_mouse_button(self) -> Option<MouseButton> {
        match self {
            BindKey::MouseLeft => Some(MouseButton::Left),
            BindKey::MouseRight => Some(MouseButton::Right),
            BindKey::MouseMiddle => Some(MouseButton::Middle),
            _ => None,
        }
    }
}

#[derive(Clone)]
struct MacroConfig {
    enable_double_edit: bool,
    enable_drag_edit: bool,
    enable_pickup: bool,
    activation_bind: BindKey,
    edit_bind: BindKey,
    select_bind: BindKey,
    pickup_bind: BindKey,
    double_edit_speed_ms: u64,
    drag_hold_ms: u64,
    pickup_speed_ms: u64,
}

impl Default for MacroConfig {
    fn default() -> Self {
        Self {
            enable_double_edit: false,
            enable_drag_edit: false,
            enable_pickup: false,
            activation_bind: BindKey::F6,
            edit_bind: BindKey::F,
            select_bind: BindKey::MouseLeft,
            pickup_bind: BindKey::E,
            double_edit_speed_ms: 35,
            drag_hold_ms: 110,
            pickup_speed_ms: 50,
        }
    }
}

fn apply_theme(style: &mut imgui::Style) {
    style.window_rounding = 8.0;
    style.frame_rounding = 6.0;
    style.grab_rounding = 6.0;
    style.tab_rounding = 6.0;

    let colors = &mut style.colors;
    colors[StyleColor::WindowBg as usize] = [0.97, 0.91, 0.95, 1.0];
    colors[StyleColor::TitleBg as usize] = [0.79, 0.89, 0.99, 1.0];
    colors[StyleColor::TitleBgActive as usize] = [0.74, 0.86, 1.0, 1.0];
    colors[StyleColor::FrameBg as usize] = [0.96, 0.84, 0.91, 0.95];
    colors[StyleColor::FrameBgHovered as usize] = [0.92, 0.78, 0.88, 1.0];
    colors[StyleColor::FrameBgActive as usize] = [0.87, 0.73, 0.84, 1.0];
    colors[StyleColor::Button as usize] = [0.72, 0.86, 0.98, 1.0];
    colors[StyleColor::ButtonHovered as usize] = [0.66, 0.81, 0.97, 1.0];
    colors[StyleColor::ButtonActive as usize] = [0.58, 0.74, 0.94, 1.0];
    colors[StyleColor::CheckMark as usize] = [0.46, 0.63, 0.92, 1.0];
    colors[StyleColor::Header as usize] = [0.96, 0.79, 0.89, 1.0];
    colors[StyleColor::HeaderHovered as usize] = [0.93, 0.74, 0.86, 1.0];
    colors[StyleColor::HeaderActive as usize] = [0.89, 0.68, 0.82, 1.0];
    colors[StyleColor::Tab as usize] = [0.85, 0.91, 0.99, 1.0];
    colors[StyleColor::TabHovered as usize] = [0.80, 0.88, 0.99, 1.0];
    colors[StyleColor::TabActive as usize] = [0.93, 0.78, 0.88, 1.0];
}

fn combo_for_bind(ui: &Ui, label: &str, current: &mut BindKey) {
    let mut index = BindKey::ALL
        .iter()
        .position(|k| *k == *current)
        .unwrap_or(0);
    let items: Vec<&str> = BindKey::ALL.iter().map(|k| k.as_str()).collect();

    if ui.combo_simple_string(label, &mut index, &items) {
        *current = BindKey::ALL[index];
    }
}

fn send_bind(enigo: &mut Enigo, bind: BindKey) {
    if let Some(mouse_button) = bind.to_mouse_button() {
        enigo.mouse_down(mouse_button);
        thread::sleep(Duration::from_millis(5));
        enigo.mouse_up(mouse_button);
        return;
    }

    if let Some(key) = bind.to_enigo_key() {
        enigo.key_down(key);
        thread::sleep(Duration::from_millis(3));
        enigo.key_up(key);
    }
}

fn run_macro_engine(config: Arc<Mutex<MacroConfig>>, running: Arc<AtomicBool>) {
    let device_state = DeviceState::new();
    let mut enigo = Enigo::new();

    let mut last_double_edit = Instant::now();
    let mut last_pickup = Instant::now();
    let mut activation_was_down = false;

    while running.load(Ordering::Relaxed) {
        let snapshot = {
            let guard = config.lock().unwrap();
            guard.clone()
        };

        let keys = device_state.get_keys();
        let activation_down = snapshot
            .activation_bind
            .to_keycode()
            .map(|k| keys.contains(&k))
            .unwrap_or(false);

        if activation_down {
            if snapshot.enable_double_edit
                && last_double_edit.elapsed()
                    >= Duration::from_millis(snapshot.double_edit_speed_ms)
            {
                send_bind(&mut enigo, snapshot.edit_bind);
                last_double_edit = Instant::now();
            }

            if snapshot.enable_pickup
                && last_pickup.elapsed() >= Duration::from_millis(snapshot.pickup_speed_ms)
            {
                send_bind(&mut enigo, snapshot.pickup_bind);
                last_pickup = Instant::now();
            }

            if snapshot.enable_drag_edit && !activation_was_down {
                send_bind(&mut enigo, snapshot.select_bind);
                enigo.mouse_down(MouseButton::Left);
                thread::sleep(Duration::from_millis(snapshot.drag_hold_ms));
                enigo.mouse_up(MouseButton::Left);
            }
        }

        activation_was_down = activation_down;
        thread::sleep(Duration::from_millis(1));
    }
}

fn draw_ui(ui: &Ui, config: &Arc<Mutex<MacroConfig>>) {
    let mut local = {
        let guard = config.lock().unwrap();
        guard.clone()
    };

    ui.window("MacroRS - Fortnite Macro Panel")
        .size([640.0, 430.0], Condition::FirstUseEver)
        .position([20.0, 20.0], Condition::FirstUseEver)
        .build(|| {
            ui.text_colored(
                [0.35, 0.42, 0.72, 1.0],
                "Configure your drag edit, double edit, and pickup automation",
            );
            ui.separator();

            if let Some(_tab_bar) = ui.tab_bar("macro_tabs") {
                if let Some(_tab) = ui.tab_item("Enablers") {
                    ui.checkbox("Enable Double Edit Macro", &mut local.enable_double_edit);
                    ui.checkbox("Enable Drag Edit Macro", &mut local.enable_drag_edit);
                    ui.checkbox("Enable Pickup Macro", &mut local.enable_pickup);
                }

                if let Some(_tab) = ui.tab_item("Speeds") {
                    ui.slider_config("Double Edit Speed (ms)", 5, 250)
                        .build(&mut local.double_edit_speed_ms);
                    ui.slider_config("Drag Hold (ms)", 5, 400)
                        .build(&mut local.drag_hold_ms);
                    ui.slider_config("Pickup Spam Speed (ms)", 5, 250)
                        .build(&mut local.pickup_speed_ms);
                }

                if let Some(_tab) = ui.tab_item("Binds") {
                    combo_for_bind(ui, "Activation Bind", &mut local.activation_bind);
                    combo_for_bind(ui, "Edit Bind", &mut local.edit_bind);
                    combo_for_bind(ui, "Select Bind", &mut local.select_bind);
                    combo_for_bind(ui, "Pickup Bind", &mut local.pickup_bind);
                    ui.text("(You can reuse the same key for multiple binds.)");
                }

                if let Some(_tab) = ui.tab_item("Info") {
                    ui.bullet_text("Hold the activation bind to run enabled macros.");
                    ui.bullet_text("Double Edit: spams edit bind at configured speed.");
                    ui.bullet_text("Drag Edit: performs a held click/drag sequence once each activation press.");
                    ui.bullet_text("Pickup: spams pickup bind at configured speed.");
                }
            }
        });

    let mut guard = config.lock().unwrap();
    *guard = local;
}

fn main() {
    let config = Arc::new(Mutex::new(MacroConfig::default()));
    let running = Arc::new(AtomicBool::new(true));

    {
        let config_clone = Arc::clone(&config);
        let running_clone = Arc::clone(&running);
        thread::spawn(move || run_macro_engine(config_clone, running_clone));
    }

    let event_loop = EventLoopBuilder::new().build().unwrap();
    let (window, display) = glium::backend::glutin::SimpleWindowBuilder::new()
        .with_title("MacroRS")
        .with_inner_size(700, 500)
        .build(&event_loop);

    let mut imgui = Context::create();
    imgui.set_ini_filename(None);
    imgui.fonts().add_font(&[FontSource::DefaultFontData {
        config: Some(FontConfig {
            size_pixels: 15.0,
            ..FontConfig::default()
        }),
    }]);

    apply_theme(imgui.style_mut());

    let mut platform = WinitPlatform::init(&mut imgui);
    platform.attach_window(imgui.io_mut(), &window, HiDpiMode::Rounded);

    let mut renderer = Renderer::init(&mut imgui, &display).unwrap();
    let mut last_frame = Instant::now();

    event_loop
        .run(move |event: Event<()>, target| {
            platform.handle_event(imgui.io_mut(), &window, &event);

            match event {
                Event::NewEvents(_) => {
                    imgui.io_mut().update_delta_time(last_frame.elapsed());
                    last_frame = Instant::now();
                }
                Event::AboutToWait => {
                    platform
                        .prepare_frame(imgui.io_mut(), &window)
                        .expect("Failed to prepare frame");
                    window.request_redraw();
                }
                Event::WindowEvent {
                    event: WindowEvent::RedrawRequested,
                    ..
                } => {
                    let ui = imgui.frame();
                    draw_ui(ui, &config);

                    let mut target_surface = display.draw();
                    target_surface.clear_color(0.95, 0.90, 0.95, 1.0);
                    platform.prepare_render(ui, &window);

                    let draw_data = imgui.render();
                    renderer
                        .render(&mut target_surface, draw_data)
                        .expect("Rendering failed");
                    target_surface.finish().expect("Swap buffers failed");
                }
                Event::WindowEvent {
                    event: WindowEvent::CloseRequested,
                    ..
                } => {
                    running.store(false, Ordering::Relaxed);
                    target.exit();
                }
                _ => {}
            }
        })
        .unwrap();
}
