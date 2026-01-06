import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import sys
import os
from script import run_scraper as run_trustoo_scraper
from werkspot_scraper import run_werkspot_scraper

class ScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Scraper - Trustoo & Werkspot")
        self.root.geometry("700x650")
        
        # Variabelen
        self.scraper_type_var = tk.StringVar(value="trustoo")  # "trustoo" of "werkspot"
        self.url_var = tk.StringVar(value="https://trustoo.nl/nederland/elektricien/")
        self.mode_var = tk.StringVar(value="new")  # "new" of "continue"
        self.csv_filename_var = tk.StringVar()
        self.excel_filename_var = tk.StringVar()
        self.is_running = False
        
        self.setup_ui()
    
    def setup_ui(self):
        # Hoofd frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Titel
        title_label = ttk.Label(main_frame, text="Scraper - Trustoo & Werkspot", font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Scraper type selectie
        scraper_frame = ttk.LabelFrame(main_frame, text="Kies Scraper", padding="10")
        scraper_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        scraper_frame.columnconfigure(0, weight=1)
        
        ttk.Radiobutton(
            scraper_frame, 
            text="Trustoo", 
            variable=self.scraper_type_var, 
            value="trustoo",
            command=self.on_scraper_change
        ).grid(row=0, column=0, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(
            scraper_frame, 
            text="Werkspot", 
            variable=self.scraper_type_var, 
            value="werkspot",
            command=self.on_scraper_change
        ).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        # URL input
        ttk.Label(main_frame, text="URL:").grid(row=2, column=0, sticky=tk.W, pady=5)
        url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=50)
        url_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Mode selectie
        mode_frame = ttk.LabelFrame(main_frame, text="Bestandsmodus", padding="10")
        mode_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        mode_frame.columnconfigure(0, weight=1)
        
        ttk.Radiobutton(
            mode_frame, 
            text="Nieuw bestand aanmaken", 
            variable=self.mode_var, 
            value="new",
            command=self.on_mode_change
        ).grid(row=0, column=0, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(
            mode_frame, 
            text="Doorgaan in bestaand bestand", 
            variable=self.mode_var, 
            value="continue",
            command=self.on_mode_change
        ).grid(row=1, column=0, sticky=tk.W, pady=5)
        
        # Bestandsnaam inputs
        file_frame = ttk.LabelFrame(main_frame, text="Bestandsnamen (optioneel)", padding="10")
        file_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Label(file_frame, text="CSV bestand:").grid(row=0, column=0, sticky=tk.W, pady=5)
        csv_frame = ttk.Frame(file_frame)
        csv_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        csv_frame.columnconfigure(0, weight=1)
        
        csv_entry = ttk.Entry(csv_frame, textvariable=self.csv_filename_var, width=40)
        csv_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        ttk.Button(
            csv_frame, 
            text="Bladeren...", 
            command=lambda: self.browse_file(self.csv_filename_var, "CSV bestanden", "*.csv")
        ).grid(row=0, column=1, padx=(5, 0))
        
        ttk.Label(file_frame, text="Excel bestand:").grid(row=1, column=0, sticky=tk.W, pady=5)
        excel_frame = ttk.Frame(file_frame)
        excel_frame.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        excel_frame.columnconfigure(0, weight=1)
        
        excel_entry = ttk.Entry(excel_frame, textvariable=self.excel_filename_var, width=40)
        excel_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        ttk.Button(
            excel_frame, 
            text="Bladeren...", 
            command=lambda: self.browse_file(self.excel_filename_var, "Excel bestanden", "*.xlsx")
        ).grid(row=0, column=1, padx=(5, 0))
        
        # Start knop
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)
        
        self.start_button = ttk.Button(
            button_frame, 
            text="Start Scrapen", 
            command=self.start_scraping,
            style="Accent.TButton"
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(
            button_frame, 
            text="Stop", 
            command=self.stop_scraping,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Output venster
        output_frame = ttk.LabelFrame(main_frame, text="Output", padding="10")
        output_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(6, weight=1)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, height=15, width=80, wrap=tk.WORD)
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status bar
        self.status_var = tk.StringVar(value="Klaar")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.grid(row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        # Initial updates
        self.on_scraper_change()
        self.on_mode_change()
    
    def on_scraper_change(self):
        """Update UI wanneer scraper type verandert."""
        scraper_type = self.scraper_type_var.get()
        
        if scraper_type == "trustoo":
            self.url_var.set("https://trustoo.nl/nederland/elektricien/")
            # Update bestandsnamen als ze leeg zijn of standaard zijn
            if not self.csv_filename_var.get() or "werkspot" in self.csv_filename_var.get().lower():
                self.csv_filename_var.set("")
            if not self.excel_filename_var.get() or "werkspot" in self.excel_filename_var.get().lower():
                self.excel_filename_var.set("")
        else:  # werkspot
            self.url_var.set("https://www.werkspot.nl/elektricien")
            # Update bestandsnamen als ze leeg zijn of standaard zijn
            if not self.csv_filename_var.get() or "trustoo" in self.csv_filename_var.get().lower():
                self.csv_filename_var.set("")
            if not self.excel_filename_var.get() or "trustoo" in self.excel_filename_var.get().lower():
                self.excel_filename_var.set("")
        
        # Update mode change om juiste bestanden te laden
        self.on_mode_change()
    
    def on_mode_change(self):
        """Update UI wanneer modus verandert."""
        if self.mode_var.get() == "continue":
            scraper_type = self.scraper_type_var.get()
            # Bij doorgaan: toon bestaande bestanden
            if scraper_type == "trustoo":
                if os.path.exists("trustoo_elektriciens.csv"):
                    self.csv_filename_var.set("trustoo_elektriciens.csv")
                if os.path.exists("trustoo_elektriciens.xlsx"):
                    self.excel_filename_var.set("trustoo_elektriciens.xlsx")
            else:  # werkspot
                if os.path.exists("werkspot_elektriciens.csv"):
                    self.csv_filename_var.set("werkspot_elektriciens.csv")
                if os.path.exists("werkspot_elektriciens.xlsx"):
                    self.excel_filename_var.set("werkspot_elektriciens.xlsx")
        # Bij nieuw bestand: leeg de velden niet, gebruiker kan zelf kiezen
    
    def browse_file(self, var, file_type, extension):
        """Open file browser."""
        filename = filedialog.asksaveasfilename(
            defaultextension=extension,
            filetypes=[(file_type, extension), ("Alle bestanden", "*.*")]
        )
        if filename:
            var.set(filename)
    
    def write_output(self, text):
        """Schrijf tekst naar output venster."""
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.root.update()
    
    def start_scraping(self):
        """Start het scrapen in een aparte thread."""
        if self.is_running:
            return
        
        # Validatie
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Fout", "Voer een URL in!")
            return
        
        if not url.startswith("http"):
            messagebox.showerror("Fout", "URL moet beginnen met http:// of https://")
            return
        
        # Clear output
        self.output_text.delete(1.0, tk.END)
        
        # Update UI
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("Scrapen gestart...")
        
        # Start in thread
        thread = threading.Thread(target=self.run_scraper_thread, daemon=True)
        thread.start()
    
    def run_scraper_thread(self):
        """Voer scraper uit in aparte thread."""
        import sys
        import io
        
        try:
            url = self.url_var.get().strip()
            mode = self.mode_var.get()
            csv_file = self.csv_filename_var.get().strip() or None
            excel_file = self.excel_filename_var.get().strip() or None
            
            # Load existing alleen als modus "continue" is
            load_existing = (mode == "continue")
            
            # Redirect stdout naar een StringIO buffer en GUI
            old_stdout = sys.stdout
            stdout_buffer = io.StringIO()
            
            class GuiOutput:
                def __init__(self, buffer, gui):
                    self.buffer = buffer
                    self.gui = gui
                
                def write(self, text):
                    self.buffer.write(text)
                    if self.gui.is_running:
                        self.gui.root.after(0, lambda t=text: self.gui.write_output(t))
                
                def flush(self):
                    pass
            
            gui_output = GuiOutput(stdout_buffer, self)
            sys.stdout = gui_output
            
            try:
                # Run de juiste scraper op basis van keuze
                scraper_type = self.scraper_type_var.get()
                if scraper_type == "trustoo":
                    companies = run_trustoo_scraper(
                        target_url=url,
                        csv_filename=csv_file,
                        excel_filename=excel_file,
                        load_existing=load_existing,
                        headless=False,
                        max_additional_pages=None
                    )
                else:  # werkspot
                    companies = run_werkspot_scraper(
                        target_url=url,
                        csv_filename=csv_file,
                        excel_filename=excel_file,
                        load_existing=load_existing,
                        headless=False,
                        max_additional_pages=None
                    )
                
                if self.is_running:
                    self.root.after(0, lambda: self.write_output(f"\n\n✅ Scrapen succesvol voltooid!\n📊 Totaal: {len(companies)} bedrijven\n"))
                    self.root.after(0, lambda: self.status_var.set(f"Klaar - {len(companies)} bedrijven verzameld"))
                    self.root.after(0, lambda: messagebox.showinfo("Succes", f"Scrapen voltooid!\n{len(companies)} bedrijven verzameld."))
            finally:
                sys.stdout = old_stdout
        
        except KeyboardInterrupt:
            if self.is_running:
                self.root.after(0, lambda: self.write_output("\n\n⚠️ Scrapen gestopt door gebruiker\n"))
                self.root.after(0, lambda: self.status_var.set("Gestopt"))
        except Exception as e:
            if self.is_running:
                error_msg = f"\n\n❌ Fout opgetreden: {str(e)}\n"
                self.root.after(0, lambda: self.write_output(error_msg))
                self.root.after(0, lambda: self.status_var.set("Fout opgetreden"))
                error_msg = str(e)
                self.root.after(0, lambda msg=error_msg: messagebox.showerror("Fout", f"Er is een fout opgetreden:\n{msg}"))
        finally:
            if self.is_running:
                self.root.after(0, self.scraping_finished)
    
    def scraping_finished(self):
        """Reset UI na scrapen."""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def stop_scraping(self):
        """Stop het scrapen."""
        if messagebox.askyesno("Bevestigen", "Weet je zeker dat je wilt stoppen?"):
            self.is_running = False
            self.status_var.set("Stoppen...")
            # Note: Dit stopt alleen de GUI, het script zelf moet worden gestopt
            # De gebruiker moet Ctrl+C gebruiken in de terminal of de browser sluiten

def main():
    root = tk.Tk()
    app = ScraperGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()

