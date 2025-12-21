import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import time
from datetime import datetime

# --- 1. CONFIGURATION & DATABASE SETUP (Unchanged) ---
DB_NAME = 'telephone_billing.db'

# Define available rate plans
RATE_PLANS = {
    "Standard": 0.05,    # $0.05 per second
    "Premium": 0.03,     # $0.03 per second
    "Business": 0.08,    # $0.08 per second
}
# Default rate when rate_plan is not implemented for cost calculation
DEFAULT_RATE_PER_SECOND = RATE_PLANS["Standard"]

def create_database():
    """Initializes the SQLite database and creates necessary tables."""
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.execute("PRAGMA foreign_keys = ON") 
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                address TEXT,
                rate_plan TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS CallLogs (
                call_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                callee_number TEXT,
                start_time TEXT,
                duration_seconds INTEGER,
                cost REAL,
                FOREIGN KEY (customer_id) REFERENCES Customers(customer_id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BillHistory (
                bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                billing_period TEXT NOT NULL,
                total_calls INTEGER,
                total_charge REAL,
                date_generated TEXT,
                FOREIGN KEY (customer_id) REFERENCES Customers(customer_id) ON DELETE CASCADE
            )
        """)
        
        conn.commit()
    except Exception as e:
        messagebox.showerror("DB Error", f"Failed to initialize database: {e}")
    finally:
        if conn:
            conn.close()

# --- 2. BUSINESS LOGIC & DATA ACCESS FUNCTIONS (Unchanged) ---

def execute_query(query, params=(), fetch_mode=None):
    """Helper function to handle all database operations."""
    conn = None
    result = None
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        if fetch_mode == 'all':
            result = cursor.fetchall()
        elif fetch_mode == 'one':
            result = cursor.fetchone()
        else:
            conn.commit()
            result = True
            
        return result
        
    except sqlite3.IntegrityError:
        messagebox.showerror("Error", "A record with this unique value already exists (e.g., phone number).")
        return None if fetch_mode else False
    except Exception as e:
        messagebox.showerror("DB Error", f"Database operation failed: {e}")
        return None if fetch_mode else False
    finally:
        if conn:
            conn.close()

def get_all_customers():
    query = "SELECT customer_id, phone_number, name, address, rate_plan FROM Customers ORDER BY customer_id DESC"
    customers = execute_query(query, fetch_mode='all')
    return customers if customers is not None else []

def add_customer(phone, name, address, rate_plan):
    query = "INSERT INTO Customers (phone_number, name, address, rate_plan) VALUES (?, ?, ?, ?)"
    if execute_query(query, (phone, name, address, rate_plan)):
        messagebox.showinfo("Success", f"Customer {name} added successfully.")
        return True
    return False

def update_customer(customer_id, phone, name, address, rate_plan):
    query = """
        UPDATE Customers 
        SET phone_number = ?, name = ?, address = ?, rate_plan = ? 
        WHERE customer_id = ?
    """
    params = (phone, name, address, rate_plan, customer_id)
    if execute_query(query, params):
        messagebox.showinfo("Success", f"Customer ID {customer_id} updated successfully.")
        return True
    return False

def delete_customer(customer_id):
    query = "DELETE FROM Customers WHERE customer_id = ?"
    if execute_query(query, (customer_id,)):
        messagebox.showinfo("Deleted", f"Customer ID {customer_id} and all related records have been deleted.")
        return True
    return False

def log_call(phone_number, callee_number, duration_seconds):
    customer_data = execute_query("SELECT customer_id, rate_plan FROM Customers WHERE phone_number = ?", 
                             (phone_number,), fetch_mode='one')
    
    if not customer_data:
        messagebox.showerror("Error", f"Customer with phone number {phone_number} not found.")
        return False
        
    customer_id, rate_plan_name = customer_data
    rate = RATE_PLANS.get(rate_plan_name, DEFAULT_RATE_PER_SECOND) 
    call_cost = duration_seconds * rate
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    query = """
        INSERT INTO CallLogs (customer_id, callee_number, start_time, duration_seconds, cost) 
        VALUES (?, ?, ?, ?, ?)
    """
    params = (customer_id, callee_number, start_time, duration_seconds, call_cost)
    
    if execute_query(query, params):
        messagebox.showinfo("Call Logged", 
                            f"Call logged for {phone_number} (Rate: {rate_plan_name}).\nDuration: {duration_seconds}s, Cost: ${call_cost:.2f}")
        return True
    return False

def generate_bill(customer_id, billing_period):
    period_filter = f"{billing_period}%"
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT SUM(cost), COUNT(call_id)
            FROM CallLogs 
            WHERE customer_id = ? AND start_time LIKE ? 
        """, (customer_id, period_filter))
        
        result = cursor.fetchone()
        
        total_charge, total_calls = result if result else (None, None)
        
        if total_calls is None or total_calls == 0:
            messagebox.showinfo("Info", "No calls found for this period to generate a bill.")
            return

        date_generated = time.strftime("%Y-%m-%d %H:%M:%S")

        exists = cursor.execute("SELECT bill_id FROM BillHistory WHERE customer_id = ? AND billing_period = ?",
                                (customer_id, billing_period)).fetchone()
        
        if exists:
            query = """
                UPDATE BillHistory SET total_calls = ?, total_charge = ?, date_generated = ?
                WHERE bill_id = ?
            """
            cursor.execute(query, (total_calls, total_charge, date_generated, exists[0]))
            conn.commit()
            messagebox.showinfo("Bill Updated", f"Bill for period {billing_period} updated.\nTotal Charge: ${total_charge:.2f}")
        else:
            query = """
                INSERT INTO BillHistory (customer_id, billing_period, total_calls, total_charge, date_generated)
                VALUES (?, ?, ?, ?, ?)
            """
            cursor.execute(query, (customer_id, billing_period, total_calls, total_charge, date_generated))
            conn.commit()
            messagebox.showinfo("Bill Generated", f"Bill for period {billing_period} generated.\nTotal Charge: ${total_charge:.2f}")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate bill: {e}")
    finally:
        if conn:
            conn.close()

# --- 3. TKINTER GUI (Presentation Layer) ---

class BillingApp:
    def __init__(self, master):
        self.master = master
        master.title("📞 Telephone Billing System (Stable CRUD)")
        master.geometry("1000x700")
        
        create_database()

        self.selected_customer_id = tk.IntVar()
        self.selected_customer_id.set(0)
        self.customer_phone_map = {}

        self.rate_plan_var = tk.StringVar(master)
        self.rate_plan_var.set(list(RATE_PLANS.keys())[0])
        
        self.notebook = ttk.Notebook(master)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")
        
        self.customer_tab = ttk.Frame(self.notebook)
        self.call_log_tab = ttk.Frame(self.notebook)
        self.billing_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.customer_tab, text="👤 Customer Management (CRUD)")
        self.notebook.add(self.call_log_tab, text="☎️ Call Logging")
        self.notebook.add(self.billing_tab, text="💰 Bill Generation & View")
        
        # --- TIMER INITIALIZATION ---
        self.timer = None # Tracks the pending single-click action
        # ----------------------------
        
        self.setup_customer_tab()
        self.setup_call_log_tab()
        self.setup_billing_tab()
        
        self.load_customers_to_treeview()
        self.update_customer_dropdowns()

    # --- Customer Tab UI ---
    def setup_customer_tab(self):
        # ... [Input fields and buttons setup remains the same] ...
        
        action_frame = ttk.Frame(self.customer_tab)
        action_frame.pack(padx=10, pady=10, fill="x")

        # --- A. Input Fields ---
        input_box = ttk.LabelFrame(action_frame, text="Customer Details")
        input_box.pack(side=tk.LEFT, padx=10, pady=5, fill="x", expand=True)

        tk.Label(input_box, text="Phone Number:").grid(row=0, column=0, padx=5, pady=2, sticky='w')
        self.phone_entry = tk.Entry(input_box, width=40)
        self.phone_entry.grid(row=0, column=1, padx=5, pady=2, sticky='we')
        
        tk.Label(input_box, text="Name:").grid(row=1, column=0, padx=5, pady=2, sticky='w')
        self.name_entry = tk.Entry(input_box, width=40)
        self.name_entry.grid(row=1, column=1, padx=5, pady=2, sticky='we')
        
        tk.Label(input_box, text="Address:").grid(row=2, column=0, padx=5, pady=2, sticky='w')
        self.address_entry = tk.Entry(input_box, width=40)
        self.address_entry.grid(row=2, column=1, padx=5, pady=2, sticky='we')
        
        tk.Label(input_box, text="Rate Plan:").grid(row=3, column=0, padx=5, pady=2, sticky='w')
        self.rate_combo = ttk.Combobox(input_box, textvariable=self.rate_plan_var, 
                                       values=list(RATE_PLANS.keys()), state='readonly', width=38)
        self.rate_combo.grid(row=3, column=1, padx=5, pady=2, sticky='we')
        
        input_box.grid_columnconfigure(1, weight=1)

        # --- B. CRUD Buttons ---
        button_box = ttk.LabelFrame(action_frame, text="Actions")
        button_box.pack(side=tk.RIGHT, padx=10, pady=5, fill="y")
        
        self.add_btn = tk.Button(button_box, text="✅ Add New Customer (Create)", 
                                 command=self.handle_add_customer, width=30)
        self.add_btn.pack(pady=5, padx=10)
        
        self.update_btn = tk.Button(button_box, text="🔄 Update Selected Customer (Update)", 
                                    command=self.handle_update_customer, state=tk.DISABLED, width=30)
        self.update_btn.pack(pady=5, padx=10)
        
        self.delete_btn = tk.Button(button_box, text="🗑️️ Delete Selected Customer (Delete)", 
                                    command=self.handle_delete_customer, state=tk.DISABLED, width=30, bg='red', fg='white')
        self.delete_btn.pack(pady=5, padx=10)
        
        self.clear_btn = tk.Button(button_box, text="Clear Selection", 
                                   command=self.clear_customer_entries, width=30)
        self.clear_btn.pack(pady=5, padx=10)


        # Treeview Frame for Displaying Customers
        display_frame = ttk.LabelFrame(self.customer_tab, text="All Registered Customers (Click for Delete, Double-Click for Update)")
        display_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.customer_tree = ttk.Treeview(display_frame, columns=('ID', 'Phone', 'Name', 'Address', 'Rate'), 
                                          show='headings', selectmode='browse')
        
        self.customer_tree.heading('ID', text='ID')
        self.customer_tree.heading('Phone', text='Phone Number')
        self.customer_tree.heading('Name', text='Name')
        self.customer_tree.heading('Address', text='Address')
        self.customer_tree.heading('Rate', text='Rate Plan')
        
        self.customer_tree.column('ID', width=50, anchor='center')
        self.customer_tree.column('Phone', width=120, anchor='w')
        self.customer_tree.column('Name', width=150, anchor='w')
        self.customer_tree.column('Address', width=250, anchor='w')
        self.customer_tree.column('Rate', width=100, anchor='center')
        
        scrollbar = ttk.Scrollbar(display_frame, orient=tk.VERTICAL, command=self.customer_tree.yview)
        self.customer_tree.configure(yscrollcommand=scrollbar.set)
        
        self.customer_tree.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side='right', fill='y')

        # FINAL ROBUST BINDINGS:
        # 1. Selection change (single click) starts the timer
        self.customer_tree.bind('<<TreeviewSelect>>', self.handle_treeview_select)
        # 2. Double click cancels the timer and runs update logic
        self.customer_tree.bind('<Double-1>', self.handle_double_click_update)


    def clear_customer_entries(self):
        """Clears inputs and resets buttons to 'Add' mode."""
        
        # Cancel the pending timer if it exists
        if self.timer:
            self.master.after_cancel(self.timer)
            self.timer = None
            
        # 1. Clear customer ID state
        self.selected_customer_id.set(0)
        
        # 2. Reset entries
        self.phone_entry.config(state=tk.NORMAL)
        self.phone_entry.delete(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.address_entry.delete(0, tk.END)
        self.rate_plan_var.set(list(RATE_PLANS.keys())[0])
        
        # 3. Reset buttons
        self.update_btn.config(state=tk.DISABLED)
        self.delete_btn.config(state=tk.DISABLED)
        self.add_btn.config(state=tk.NORMAL)
        
        # 4. Clear Treeview selection defensively
        if self.customer_tree.selection():
            self.customer_tree.selection_remove(self.customer_tree.selection())

    def execute_single_click_delete(self):
        """
        Action performed when the single-click timer expires. 
        Sets buttons to Delete Mode.
        """
        selected_items = self.customer_tree.selection()
        
        if not selected_items:
            self.clear_customer_entries()
            return
            
        values = self.customer_tree.item(selected_items[0], 'values')
        
        if values:
            self.selected_customer_id.set(values[0])
            
            # 1. Clear input entries 
            self.phone_entry.config(state=tk.NORMAL)
            self.phone_entry.delete(0, tk.END)
            self.name_entry.delete(0, tk.END)
            self.address_entry.delete(0, tk.END)
            self.rate_plan_var.set(list(RATE_PLANS.keys())[0])

            # 2. Set button states to Delete mode
            self.update_btn.config(state=tk.DISABLED)
            self.delete_btn.config(state=tk.NORMAL) 
            self.add_btn.config(state=tk.NORMAL)
        
        self.timer = None # Clear timer reference

    def handle_treeview_select(self, event):
        """
        On selection, cancel any existing timer and start a new one.
        If a double-click happens, it will cancel this new timer.
        """
        selected_items = self.customer_tree.selection()

        if not selected_items:
            self.clear_customer_entries()
            return

        # 1. Cancel any previous pending action
        if self.timer:
            self.master.after_cancel(self.timer)
        
        # 2. Set a new timer for the single-click action (250ms is standard)
        self.timer = self.master.after(250, self.execute_single_click_delete)
        
        # return "break" is NOT used here, as we want the Treeview selection to proceed normally.

    def handle_double_click_update(self, event):
        """
        Handles the double-click. Cancels the timer and executes Update logic.
        """
        # CRITICAL: Cancel the single-click timer immediately
        if self.timer:
            self.master.after_cancel(self.timer)
            self.timer = None
        
        # Get the item clicked
        selected_item = self.customer_tree.identify_row(event.y)

        if not selected_item:
            self.clear_customer_entries()
            return
            
        values = self.customer_tree.item(selected_item, 'values')
        
        if values:
            
            # 1. Clear inputs first
            self.phone_entry.config(state=tk.NORMAL) 
            self.phone_entry.delete(0, tk.END)
            self.name_entry.delete(0, tk.END)
            self.address_entry.delete(0, tk.END)
            
            # 2. Populate fields
            self.selected_customer_id.set(values[0])
            self.phone_entry.insert(0, values[1])
            self.name_entry.insert(0, values[2])
            self.address_entry.insert(0, values[3])
            self.rate_plan_var.set(values[4])
            
            # 3. Disable phone number entry when updating
            self.phone_entry.config(state=tk.DISABLED) 
            
            # 4. Set button states to Update mode (Update enabled, Add disabled)
            self.update_btn.config(state=tk.NORMAL)
            self.delete_btn.config(state=tk.NORMAL) 
            self.add_btn.config(state=tk.DISABLED)
            
            # Return "break" to stop the double-click event from generating any further 
            # single-click behavior (though the timer cancellation is the main fix).
            return "break"


    # --- CRUD Handlers (Unchanged) ---
    def handle_add_customer(self):
        self.phone_entry.config(state=tk.NORMAL)
        phone = self.phone_entry.get()
        name = self.name_entry.get()
        address = self.address_entry.get()
        rate = self.rate_plan_var.get()

        if phone and name and rate in RATE_PLANS:
            if add_customer(phone, name, address, rate):
                self.clear_customer_entries()
                self.load_customers_to_treeview()
                self.update_customer_dropdowns()  
        else:
            messagebox.showwarning("Input Error", "Phone Number, Name, and a valid Rate Plan are required.")
            
        self.phone_entry.config(state=tk.NORMAL)

    def handle_update_customer(self):
        cust_id = self.selected_customer_id.get()
        phone = self.phone_entry.get() 
        name = self.name_entry.get()
        address = self.address_entry.get()
        rate = self.rate_plan_var.get()
        
        if cust_id <= 0:
            messagebox.showwarning("Error", "No customer selected for update.")
            return

        if phone and name and rate in RATE_PLANS:
            self.phone_entry.config(state=tk.NORMAL) 
            
            if update_customer(cust_id, phone, name, address, rate):
                self.clear_customer_entries()
                self.load_customers_to_treeview()
                self.update_customer_dropdowns()
            else:
                self.phone_entry.config(state=tk.DISABLED)
                messagebox.showerror("Update Failed", "The customer update could not be completed.")
        else:
            messagebox.showwarning("Error", "Required fields are empty/invalid.")

    def handle_delete_customer(self):
        cust_id = self.selected_customer_id.get()
        name = "Unknown" 
        
        try:
             selected_item = self.customer_tree.selection()[0]
             name = self.customer_tree.item(selected_item, 'values')[2]
        except (IndexError, AttributeError):
             pass

        if cust_id <= 0:
            messagebox.showwarning("Error", "No customer selected for deletion.")
            return

        if cust_id:
            confirm = messagebox.askyesno("Confirm Deletion", 
                                          f"Are you sure you want to DELETE Customer ID {cust_id} ({name})? This will also delete ALL their associated call logs and bills due to CASCADE constraint.")
            if confirm:
                self.phone_entry.config(state=tk.NORMAL) 
                if delete_customer(cust_id):
                    self.clear_customer_entries()
                    self.load_customers_to_treeview()
                    self.update_customer_dropdowns()
                else:
                    messagebox.showerror("Deletion Failed", "The customer deletion could not be completed.")
                    self.phone_entry.config(state=tk.DISABLED)
        else:
            messagebox.showwarning("Error", "No customer selected for deletion.")


    def load_customers_to_treeview(self):
        if self.customer_tree.selection():
             self.customer_tree.selection_remove(self.customer_tree.selection())

        for item in self.customer_tree.get_children():
            self.customer_tree.delete(item)
            
        customers = get_all_customers()
        
        for customer_record in customers:
            self.customer_tree.insert('', tk.END, values=customer_record)
    
    # --- Dropdown, Call Log, and Billing Functions (Omitted for brevity, assumed stable) ---
    def update_customer_dropdowns(self):
        customers = get_all_customers()
        customer_options = []
        self.customer_phone_map = {}
        for cust_id, phone, name, _, _ in customers: 
            display_name = f"{name} ({phone})"
            customer_options.append(display_name)
            self.customer_phone_map[display_name] = {'id': cust_id, 'phone': phone}

        if hasattr(self, 'call_customer_dropdown'):
            self.call_customer_dropdown['values'] = customer_options
            if customer_options:
                current_call_selection = self.call_customer_var.get()
                if current_call_selection in customer_options:
                    self.call_customer_var.set(current_call_selection)
                else:
                    self.call_customer_var.set(customer_options[0])
            else:
                 self.call_customer_var.set('')

        if hasattr(self, 'bill_customer_dropdown'):
            self.bill_customer_dropdown['values'] = customer_options
            if customer_options:
                current_bill_selection = self.bill_customer_var.get()
                if current_bill_selection in customer_options:
                    self.bill_customer_var.set(current_bill_selection)
                else:
                    new_selection = customer_options[0]
                    self.bill_customer_var.set(new_selection)
                    self.handle_customer_select(new_selection)
            else:
                self.bill_customer_var.set('')
                self.handle_customer_select('')

    def setup_call_log_tab(self):
        log_frame = ttk.LabelFrame(self.call_log_tab, text="Log New Call")
        log_frame.pack(padx=10, pady=10, fill="x")

        self.call_customer_var = tk.StringVar(log_frame)
        
        tk.Label(log_frame, text="Calling Customer:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.call_customer_dropdown = ttk.Combobox(log_frame, textvariable=self.call_customer_var, 
                                                   state='readonly', width=50)
        self.call_customer_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky='we')

        tk.Label(log_frame, text="Callee Number:").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.callee_entry = tk.Entry(log_frame, width=50)
        self.callee_entry.grid(row=1, column=1, padx=5, pady=5, sticky='we')

        tk.Label(log_frame, text="Duration (seconds):").grid(row=2, column=0, padx=5, pady=5, sticky='w')
        self.duration_entry = tk.Entry(log_frame, width=50)
        self.duration_entry.grid(row=2, column=1, padx=5, pady=5, sticky='we')
        self.duration_entry.insert(0, "60") 

        log_btn = tk.Button(log_frame, text="📞 Log Call", 
                            command=self.handle_log_call)
        log_btn.grid(row=3, column=1, padx=5, pady=10, sticky='e')

    def handle_log_call(self):
        selected_customer = self.call_customer_var.get()
        callee = self.callee_entry.get()
        duration_str = self.duration_entry.get()
        
        if not selected_customer or not callee or not duration_str:
            messagebox.showwarning("Input Error", "All fields are required.")
            return

        try:
            duration = int(duration_str)
            if duration <= 0:
                 messagebox.showwarning("Input Error", "Duration must be a positive integer.")
                 return
        except ValueError:
            messagebox.showwarning("Input Error", "Duration must be an integer.")
            return

        calling_phone = self.customer_phone_map.get(selected_customer, {}).get('phone')
        
        if calling_phone:
            if log_call(calling_phone, callee, duration):
                self.callee_entry.delete(0, tk.END)
        else:
            messagebox.showerror("Error", "Selected customer data not found.")

    def setup_billing_tab(self):
        control_frame = ttk.LabelFrame(self.billing_tab, text="Bill Generation Controls")
        control_frame.pack(padx=10, pady=10, fill="x")

        self.bill_customer_var = tk.StringVar(control_frame)
        self.billing_period_var = tk.StringVar(control_frame)
        self.billing_period_var.set(datetime.now().strftime("%Y-%m"))

        tk.Label(control_frame, text="Select Customer:").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.bill_customer_dropdown = ttk.Combobox(control_frame, textvariable=self.bill_customer_var, 
                                                   state='readonly', width=40)
        self.bill_customer_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky='we')
        self.bill_customer_dropdown.bind("<<ComboboxSelected>>", lambda e: self.handle_customer_select(self.bill_customer_var.get()))

        tk.Label(control_frame, text="Billing Period (YYYY-MM):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        period_entry = tk.Entry(control_frame, textvariable=self.billing_period_var, width=40)
        period_entry.grid(row=1, column=1, padx=5, pady=5, sticky='we')

        gen_btn = tk.Button(control_frame, text="💸 Generate/Recalculate Bill", 
                            command=self.handle_generate_bill)
        gen_btn.grid(row=2, column=0, padx=5, pady=10, sticky='w')

        view_btn = tk.Button(control_frame, text="🔄 View Customer Bills", 
                            command=lambda: self.handle_customer_select(self.bill_customer_var.get()))
        view_btn.grid(row=2, column=1, padx=5, pady=10, sticky='e')
        
        display_frame = ttk.LabelFrame(self.billing_tab, text="Bill History")
        display_frame.pack(padx=10, pady=10, fill="both", expand=True)

        self.bill_tree = ttk.Treeview(display_frame, columns=('ID', 'Period', 'Calls', 'Charge', 'Generated'), show='headings')
        self.bill_tree.heading('ID', text='Bill ID')
        self.bill_tree.heading('Period', text='Billing Period')
        self.bill_tree.heading('Calls', text='Total Calls')
        self.bill_tree.heading('Charge', text='Total Charge')
        self.bill_tree.heading('Generated', text='Date Generated')
        
        self.bill_tree.column('ID', width=50, anchor='center')
        self.bill_tree.column('Period', width=120, anchor='center')
        self.bill_tree.column('Calls', width=100, anchor='center')
        self.bill_tree.column('Charge', width=100, anchor='e')
        self.bill_tree.column('Generated', width=200, anchor='w')
        
        scrollbar = ttk.Scrollbar(display_frame, orient=tk.VERTICAL, command=self.bill_tree.yview)
        self.bill_tree.configure(yscrollcommand=scrollbar.set)
        
        self.bill_tree.pack(fill="both", expand=True)
        scrollbar.pack(side='right', fill='y')

    def handle_generate_bill(self):
        selected_customer = self.bill_customer_var.get()
        billing_period = self.billing_period_var.get()

        if not selected_customer or not billing_period:
            messagebox.showwarning("Input Error", "Please select a customer and specify the billing period.")
            return

        cust_data = self.customer_phone_map.get(selected_customer, {})
        customer_id = cust_data.get('id')
        
        if customer_id:
            generate_bill(customer_id, billing_period)
            self.handle_customer_select(selected_customer)

    def handle_customer_select(self, customer_display_name):
        
        for item in self.bill_tree.get_children():
            self.bill_tree.delete(item)

        cust_data = self.customer_phone_map.get(customer_display_name, {})
        customer_id = cust_data.get('id')
        
        if not customer_id:
            return

        query = """
            SELECT bill_id, billing_period, total_calls, total_charge, date_generated 
            FROM BillHistory 
            WHERE customer_id = ? 
            ORDER BY billing_period DESC
        """
        bills = execute_query(query, (customer_id,), fetch_mode='all')
        
        if bills is None:
             return
             
        for bill_id, period, calls, charge, generated in bills:
            charge_formatted = f"${charge:.2f}"
            self.bill_tree.insert('', tk.END, values=(bill_id, period, calls, charge_formatted, generated))

# --- 4. MAIN EXECUTION ---
if __name__ == '__main__':
    root = tk.Tk()
    app = BillingApp(root)
    root.mainloop()
