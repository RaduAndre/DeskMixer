import tkinter as tk
from tkinter import ttk
from utils.error_handler import handle_error, log_error


class VolumeTab:
    """Volume control tab UI"""

    def __init__(self, parent, audio_manager, window_monitor):
        self.audio_manager = audio_manager
        self.window_monitor = window_monitor
        self.frame = tk.Frame(parent, bg="#1e1e1e")
        self.app_sliders = {}
        self.focused_app_name = None

        self._create_ui()

        # Add periodic volume update
        self.frame.after(100, self._periodic_update)

    def _create_ui(self):
        """Create the volume control UI"""
        try:
            # System Audio Section (Compact)
            system_frame = tk.LabelFrame(
                self.frame,
                text="System Audio",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=8,
                pady=8
            )
            system_frame.pack(fill="x", padx=10, pady=5)

            self._create_system_controls(system_frame)

            # Focused Application Section (Compact)
            focused_frame = tk.LabelFrame(
                self.frame,
                text="Focused Application",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=8,
                pady=8
            )
            focused_frame.pack(fill="x", padx=10, pady=5)

            self._create_focused_controls(focused_frame)

            # Applications Volume Section
            apps_frame = tk.LabelFrame(
                self.frame,
                text="Application Volumes",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 10, "bold"),
                padx=8,
                pady=8
            )
            apps_frame.pack(fill="both", expand=True, padx=10, pady=5)

            self._create_apps_list(apps_frame)

            # Refresh button
            refresh_btn = tk.Button(
                self.frame,
                text="🔄 Refresh Applications",
                command=self.refresh_applications,
                bg="#404040",
                fg="white",
                font=("Arial", 9, "bold"),
                relief="flat",
                padx=15,
                pady=6,
                cursor="hand2"
            )
            refresh_btn.pack(pady=8)

            # Initial load
            self.refresh_applications()

        except Exception as e:
            handle_error(e, "Failed to create volume tab UI")

    def _create_system_controls(self, parent):
        """Create system volume controls"""
        try:
            container = tk.Frame(parent, bg="#2d2d2d")
            container.pack(fill="x")

            # Master Volume
            master_frame = tk.Frame(container, bg="#2d2d2d")
            master_frame.pack(side="left", padx=10, pady=5)

            tk.Label(
                master_frame,
                text="🔊 Master",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 9)
            ).pack()

            self.master_slider = tk.Scale(
                master_frame,
                from_=100,
                to=0,
                command=self._set_master_volume,
                bg="#2d2d2d",
                fg="white",
                highlightthickness=0,
                length=80,
                width=20,
                showvalue=0
            )
            self.master_slider.pack()

            self.master_label = tk.Label(
                master_frame,
                text="0%",
                bg="#2d2d2d",
                fg="#00ff00",
                font=("Arial", 9, "bold")
            )
            self.master_label.pack()

            # Set initial value
            try:
                current_vol = self.audio_manager.get_master_volume()
                self.master_slider.set(int(current_vol * 100))
            except:
                self.master_slider.set(50)

            # Microphone Volume
            if self.audio_manager.has_microphone():
                mic_frame = tk.Frame(container, bg="#2d2d2d")
                mic_frame.pack(side="left", padx=10, pady=5)

                tk.Label(
                    mic_frame,
                    text="🎤 Microphone",
                    bg="#2d2d2d",
                    fg="white",
                    font=("Arial", 9)
                ).pack()

                self.mic_slider = tk.Scale(
                    mic_frame,
                    from_=100,
                    to=0,
                    command=self._set_mic_volume,
                    bg="#2d2d2d",
                    fg="white",
                    highlightthickness=0,
                    length=80,
                    width=20,
                    showvalue=0
                )
                self.mic_slider.pack()

                self.mic_label = tk.Label(
                    mic_frame,
                    text="0%",
                    bg="#2d2d2d",
                    fg="#00ff00",
                    font=("Arial", 9, "bold")
                )
                self.mic_label.pack()

                try:
                    current_vol = self.audio_manager.get_mic_volume()
                    self.mic_slider.set(int(current_vol * 100))
                except:
                    self.mic_slider.set(50)

        except Exception as e:
            log_error(e, "Error creating system controls")

    def _create_focused_controls(self, parent):
        """Create focused application controls"""
        try:
            container = tk.Frame(parent, bg="#2d2d2d")
            container.pack(fill="x")

            info_frame = tk.Frame(container, bg="#2d2d2d")
            info_frame.pack(side="left", fill="x", expand=True, padx=5)

            self.focused_app_label = tk.Label(
                info_frame,
                text="No application detected",
                bg="#2d2d2d",
                fg="#ffaa00",
                font=("Arial", 10, "bold"),
                anchor="w"
            )
            self.focused_app_label.pack(fill="x", pady=2)

            self.focused_status_label = tk.Label(
                info_frame,
                text="Waiting for audio...",
                bg="#2d2d2d",
                fg="#888888",
                font=("Arial", 8),
                anchor="w"
            )
            self.focused_status_label.pack(fill="x")

            # Slider frame
            slider_frame = tk.Frame(container, bg="#2d2d2d")
            slider_frame.pack(side="right", padx=10)

            self.focused_slider = tk.Scale(
                slider_frame,
                from_=100,
                to=0,
                command=self._set_focused_volume,
                bg="#2d2d2d",
                fg="white",
                highlightthickness=0,
                length=80,
                width=20,
                state="disabled",
                showvalue=0
            )
            self.focused_slider.pack()

            self.focused_volume_label = tk.Label(
                slider_frame,
                text="--",
                bg="#2d2d2d",
                fg="white",
                font=("Arial", 9, "bold")
            )
            self.focused_volume_label.pack()

        except Exception as e:
            log_error(e, "Error creating focused controls")

    def _create_apps_list(self, parent):
        """Create scrollable applications list"""
        try:
            # Create canvas and scrollbar
            canvas = tk.Canvas(parent, bg="#2d2d2d", highlightthickness=0)
            scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)

            self.apps_container = tk.Frame(canvas, bg="#2d2d2d")

            self.apps_container.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=self.apps_container, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Mouse wheel scrolling
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        except Exception as e:
            log_error(e, "Error creating apps list")

    def _set_master_volume(self, value):
        """Set master volume"""
        try:
            volume = int(value) / 100
            self.audio_manager.set_master_volume(volume)
            self.master_label.config(text=f"{int(value)}%")
        except Exception as e:
            log_error(e, "Error setting master volume")

    def _set_mic_volume(self, value):
        """Set microphone volume"""
        try:
            volume = int(value) / 100
            self.audio_manager.set_mic_volume(volume)
            self.mic_label.config(text=f"{int(value)}%")
        except Exception as e:
            log_error(e, "Error setting microphone volume")

    def _set_focused_volume(self, value):
        """Set focused application volume"""
        try:
            if self.focused_app_name:
                volume = int(value) / 100
                self.audio_manager.set_app_volume(self.focused_app_name, volume)
                self.focused_volume_label.config(text=f"{int(value)}%")
        except Exception as e:
            log_error(e, "Error setting focused app volume")

    def _set_app_volume(self, app_name, value):
        """Set individual application volume"""
        try:
            volume = int(value) / 100
            self.audio_manager.set_app_volume(app_name, volume)

            if app_name in self.app_sliders:
                _, label = self.app_sliders[app_name]
                label.config(text=f"{int(value)}%")
        except Exception as e:
            log_error(e, f"Error setting volume for {app_name}")

    def update_focused_app(self, app_name):
        """Update the focused application display"""
        try:
            if app_name != self.focused_app_name:
                self.focused_app_name = app_name
                self.focused_app_label.config(text=app_name)

                # Check if app has audio session
                volume = self.audio_manager.get_app_volume(app_name)

                if volume is not None:
                    self.focused_slider.config(state="normal")
                    self.focused_slider.set(int(volume * 100))
                    self.focused_volume_label.config(text=f"{int(volume * 100)}%")
                    self.focused_status_label.config(
                        text="Audio session active",
                        fg="#00ff00"
                    )
                else:
                    self.focused_slider.config(state="disabled")
                    self.focused_volume_label.config(text="--")
                    self.focused_status_label.config(
                        text="No audio session",
                        fg="#888888"
                    )
        except Exception as e:
            log_error(e, "Error updating focused app")

    def refresh_applications(self):
        """Refresh the list of applications with audio sessions"""
        try:
            # Clear existing sliders
            for widget in self.apps_container.winfo_children():
                widget.destroy()

            self.app_sliders.clear()

            # Get all applications with audio
            apps = self.audio_manager.get_all_audio_apps()

            if not apps:
                no_apps_label = tk.Label(
                    self.apps_container,
                    text="No applications with audio detected",
                    bg="#2d2d2d",
                    fg="#888888",
                    font=("Arial", 10),
                    pady=20
                )
                no_apps_label.pack()
                return

            # Create slider for each application
            for app_name, volume in apps.items():
                self._create_app_slider(app_name, volume)

        except Exception as e:
            handle_error(e, "Error refreshing applications")

    def _create_app_slider(self, app_name, volume):
        """Create a slider for an application"""
        try:
            app_frame = tk.Frame(self.apps_container, bg="#353535", padx=8, pady=6)
            app_frame.pack(fill="x", padx=5, pady=3)

            # Application icon/name (now on the right side)
            volume_label = tk.Label(
                app_frame,
                text=f"{int(volume * 100)}%",
                bg="#353535",
                fg="#00ff00",
                font=("Arial", 9, "bold"),
                width=5
            )
            volume_label.pack(side="right", padx=5)

            # Mute button
            mute_btn = tk.Button(
                app_frame,
                text="🔇",
                command=lambda: self._toggle_mute(app_name),
                bg="#404040",
                fg="white",
                font=("Arial", 10),
                relief="flat",
                padx=8,
                pady=2,
                cursor="hand2"
            )
            mute_btn.pack(side="right", padx=5)

            # Volume slider (now on the right side)
            slider = tk.Scale(
                app_frame,
                from_=100,
                to=0,
                orient="horizontal",
                command=lambda v, name=app_name: self._set_app_volume(name, v),
                bg="#353535",
                fg="white",
                highlightthickness=0,
                length=150,
                showvalue=0
            )
            slider.set(int(volume * 100))
            slider.pack(side="right", padx=5)

            # Application icon/name (now on the left side)
            label = tk.Label(
                app_frame,
                text=f"🎵 {app_name}",
                bg="#353535",
                fg="white",
                font=("Arial", 9),
                width=25,
                anchor="w"
            )
            label.pack(side="left", padx=5, fill="x", expand=True)

            self.app_sliders[app_name] = (slider, volume_label)

        except Exception as e:
            log_error(e, f"Error creating slider for {app_name}")

    def _toggle_mute(self, app_name):
        """Toggle mute for an application"""
        try:
            self.audio_manager.toggle_app_mute(app_name)
            # Refresh to update UI
            self.refresh_applications()
        except Exception as e:
            log_error(e, f"Error toggling mute for {app_name}")

    def update_volumes(self):
        """Update all volume sliders with current system values"""
        try:
            # Update master volume
            master_vol = self.audio_manager.get_master_volume()
            self.master_slider.set(int(master_vol * 100))
            self.master_label.config(text=f"{int(master_vol * 100)}%")

            # Update mic volume if available
            if self.audio_manager.has_microphone():
                mic_vol = self.audio_manager.get_mic_volume()
                self.mic_slider.set(int(mic_vol * 100))
                self.mic_label.config(text=f"{int(mic_vol * 100)}%")

            # Update application volumes
            self.refresh_applications()

        except Exception as e:
            log_error(e, "Error updating volume displays")

    def _periodic_update(self):
        """Periodically update volume displays"""
        self.update_volumes()
        self.frame.after(100, self._periodic_update)
