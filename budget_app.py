"""
Budget App — Desktop GUI
Requires: Python 3.8+, matplotlib (pip install matplotlib)
Run: python budget_app.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import os
import datetime
import calendar
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.patches as mpatches

# ─── THEME ────────────────────────────────────────────────────────────────────
BG        = "#0F1923"
PANEL     = "#162230"
CARD      = "#1E2F40"
ACCENT    = "#F0A500"
ACCENT2   = "#3BC4A0"
DANGER    = "#E05C5C"
TEXT      = "#EAF0F6"
SUBTEXT   = "#7A9AB5"
BORDER    = "#243447"

FONT_H1   = ("Georgia", 22, "bold")
FONT_H2   = ("Georgia", 14, "bold")
FONT_BODY = ("Helvetica", 11)
FONT_SMALL= ("Helvetica", 9)
FONT_MONO = ("Courier", 10)

CATEGORIES = [
    "Housing", "Food & Dining", "Transportation", "Utilities",
    "Healthcare", "Entertainment", "Shopping", "Education",
    "Savings", "Income", "Other"
]

CAT_COLORS = {
    "Housing":        "#4A90D9",
    "Food & Dining":  "#F0A500",
    "Transportation": "#3BC4A0",
    "Utilities":      "#9B59B6",
    "Healthcare":     "#E05C5C",
    "Entertainment":  "#F39C12",
    "Shopping":       "#1ABC9C",
    "Education":      "#2980B9",
    "Savings":        "#27AE60",
    "Income":         "#2ECC71",
    "Other":          "#7A9AB5",
}

# ─── DATABASE ─────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.expanduser("~"), ".budget_app.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            type        TEXT NOT NULL CHECK(type IN ('income','expense')),
            amount      REAL NOT NULL,
            category    TEXT NOT NULL,
            description TEXT,
            date        TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS goals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            target      REAL NOT NULL,
            saved       REAL NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL
        );
        """)

# ─── DATA HELPERS ─────────────────────────────────────────────────────────────
def add_transaction(type_, amount, category, description, date):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transactions (type,amount,category,description,date) VALUES (?,?,?,?,?)",
            (type_, amount, category, description, date)
        )

def get_transactions(month=None, year=None):
    with get_conn() as conn:
        if month and year:
            prefix = f"{year}-{month:02d}"
            return conn.execute(
                "SELECT * FROM transactions WHERE date LIKE ? ORDER BY date DESC",
                (f"{prefix}%",)
            ).fetchall()
        return conn.execute("SELECT * FROM transactions ORDER BY date DESC").fetchall()

def delete_transaction(tid):
    with get_conn() as conn:
        conn.execute("DELETE FROM transactions WHERE id=?", (tid,))

def get_goals():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM goals ORDER BY id").fetchall()

def add_goal(name, target):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO goals (name,target,saved,created_at) VALUES (?,?,0,?)",
            (name, target, datetime.date.today().isoformat())
        )

def update_goal_saved(gid, amount):
    with get_conn() as conn:
        conn.execute("UPDATE goals SET saved=saved+? WHERE id=?", (amount, gid))

def delete_goal(gid):
    with get_conn() as conn:
        conn.execute("DELETE FROM goals WHERE id=?", (gid,))

def monthly_summary(month, year):
    rows = get_transactions(month, year)
    income   = sum(r["amount"] for r in rows if r["type"] == "income")
    expenses = sum(r["amount"] for r in rows if r["type"] == "expense")
    by_cat   = {}
    for r in rows:
        if r["type"] == "expense":
            by_cat[r["category"]] = by_cat.get(r["category"], 0) + r["amount"]
    return income, expenses, by_cat

# ─── STYLED WIDGETS ───────────────────────────────────────────────────────────
def styled_btn(parent, text, command, color=ACCENT, fg=BG, **kw):
    b = tk.Button(parent, text=text, command=command,
                  bg=color, fg=fg, font=FONT_BODY,
                  relief="flat", cursor="hand2",
                  padx=14, pady=6, **kw)
    b.bind("<Enter>", lambda e: b.config(bg=_lighten(color)))
    b.bind("<Leave>", lambda e: b.config(bg=color))
    return b

def _lighten(hex_color):
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = min(255, r + 30)
    g = min(255, g + 30)
    b = min(255, b + 30)
    return f"#{r:02X}{g:02X}{b:02X}"

def card_frame(parent, **kw):
    return tk.Frame(parent, bg=CARD, bd=0, relief="flat", **kw)

def label(parent, text, font=FONT_BODY, fg=TEXT, **kw):
    return tk.Label(parent, text=text, font=font, fg=fg, bg=parent["bg"], **kw)

# ─── MAIN APP ─────────────────────────────────────────────────────────────────
class BudgetApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Budget — Personal Finance")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(bg=BG)
        self.resizable(True, True)

        init_db()
        self._build_ui()

    def _build_ui(self):
        # ── Sidebar ──
        sidebar = tk.Frame(self, bg=PANEL, width=180)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        label(sidebar, "💰 Budget", font=FONT_H2, fg=ACCENT).pack(pady=(28, 4), padx=16, anchor="w")
        label(sidebar, "Personal Finance", font=FONT_SMALL, fg=SUBTEXT).pack(padx=16, anchor="w")

        tk.Frame(sidebar, bg=BORDER, height=1).pack(fill="x", padx=16, pady=20)

        self.pages = {}
        self.active_nav = tk.StringVar(value="Dashboard")
        nav_items = [
            ("📊  Dashboard",   "Dashboard"),
            ("💳  Transactions","Transactions"),
            ("🎯  Goals",       "Goals"),
            ("📈  Reports",     "Reports"),
        ]
        self._nav_btns = {}
        for label_text, key in nav_items:
            btn = tk.Button(sidebar, text=label_text, anchor="w",
                            bg=PANEL, fg=TEXT, font=FONT_BODY,
                            relief="flat", cursor="hand2",
                            padx=20, pady=10, bd=0,
                            command=lambda k=key: self.show_page(k))
            btn.pack(fill="x")
            self._nav_btns[key] = btn

        # ── Content area ──
        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side="left", fill="both", expand=True)

        # Build all pages
        self.pages["Dashboard"]    = DashboardPage(self.content, self)
        self.pages["Transactions"] = TransactionsPage(self.content, self)
        self.pages["Goals"]        = GoalsPage(self.content, self)
        self.pages["Reports"]      = ReportsPage(self.content, self)

        self.show_page("Dashboard")

    def show_page(self, name):
        for k, p in self.pages.items():
            p.pack_forget()
            self._nav_btns[k].config(bg=PANEL, fg=TEXT)
        self.pages[name].pack(fill="both", expand=True)
        self._nav_btns[name].config(bg=CARD, fg=ACCENT)
        self.active_nav.set(name)
        if hasattr(self.pages[name], "refresh"):
            self.pages[name].refresh()

    def refresh_all(self):
        for p in self.pages.values():
            if hasattr(p, "refresh"):
                p.refresh()

# ─── DASHBOARD ────────────────────────────────────────────────────────────────
class DashboardPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        now = datetime.date.today()
        self.month = now.month
        self.year  = now.year

        # Header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=30, pady=(24, 0))
        label(hdr, "Dashboard", font=FONT_H1).pack(side="left")
        self.month_lbl = label(hdr, "", fg=SUBTEXT)
        self.month_lbl.pack(side="right", pady=8)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30, pady=12)

        # KPI cards row
        self.kpi_row = tk.Frame(self, bg=BG)
        self.kpi_row.pack(fill="x", padx=30)

        # Chart + recent row
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="both", expand=True, padx=30, pady=16)

        self.chart_frame = card_frame(bottom)
        self.chart_frame.pack(side="left", fill="both", expand=True, padx=(0,12))

        self.recent_frame = card_frame(bottom, width=280)
        self.recent_frame.pack(side="right", fill="y")
        self.recent_frame.pack_propagate(False)

        self.refresh()

    def refresh(self):
        now = datetime.date.today()
        income, expenses, by_cat = monthly_summary(self.month, self.year)
        net = income - expenses
        month_name = calendar.month_name[self.month]
        self.month_lbl.config(text=f"{month_name} {self.year}")

        # KPI cards
        for w in self.kpi_row.winfo_children():
            w.destroy()
        kpis = [
            ("Income",   f"${income:,.2f}",   ACCENT2),
            ("Expenses", f"${expenses:,.2f}",  DANGER),
            ("Net",      f"${net:,.2f}",       ACCENT if net >= 0 else DANGER),
        ]
        for title, val, color in kpis:
            c = card_frame(self.kpi_row)
            c.pack(side="left", expand=True, fill="both", padx=(0,12), ipady=10)
            label(c, title, font=FONT_SMALL, fg=SUBTEXT).pack(anchor="w", padx=18, pady=(14,2))
            label(c, val, font=("Georgia", 20, "bold"), fg=color).pack(anchor="w", padx=18, pady=(0,14))

        # Donut chart
        for w in self.chart_frame.winfo_children():
            w.destroy()
        label(self.chart_frame, "Spending by Category", font=FONT_H2, fg=TEXT).pack(anchor="w", padx=16, pady=(14,6))
        if by_cat:
            fig = Figure(figsize=(4.5, 3.2), dpi=90, facecolor=CARD)
            ax = fig.add_subplot(111)
            ax.set_facecolor(CARD)
            cats   = list(by_cat.keys())
            vals   = list(by_cat.values())
            colors = [CAT_COLORS.get(c, "#7A9AB5") for c in cats]
            wedges, _ = ax.pie(vals, colors=colors, startangle=90,
                                wedgeprops=dict(width=0.55, edgecolor=CARD))
            ax.set_title("", color=TEXT)
            legend_patches = [mpatches.Patch(color=colors[i], label=f"{cats[i]}  ${vals[i]:,.0f}")
                              for i in range(len(cats))]
            ax.legend(handles=legend_patches, loc="center left",
                      bbox_to_anchor=(1, 0.5), fontsize=7,
                      facecolor=CARD, edgecolor=BORDER, labelcolor=TEXT)
            fig.tight_layout(pad=1.2)
            canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=(0,10))
        else:
            label(self.chart_frame, "No expense data this month.", fg=SUBTEXT).pack(pady=40)

        # Recent transactions
        for w in self.recent_frame.winfo_children():
            w.destroy()
        label(self.recent_frame, "Recent", font=FONT_H2, fg=TEXT).pack(anchor="w", padx=14, pady=(14,6))
        rows = get_transactions(self.month, self.year)[:6]
        if not rows:
            label(self.recent_frame, "No transactions yet.", fg=SUBTEXT).pack(pady=20)
        for r in rows:
            row_f = tk.Frame(self.recent_frame, bg=CARD)
            row_f.pack(fill="x", padx=10, pady=3)
            color = ACCENT2 if r["type"] == "income" else DANGER
            sign  = "+" if r["type"] == "income" else "−"
            label(row_f, r["category"][:14], font=FONT_SMALL, fg=TEXT).pack(side="left", padx=8, pady=6)
            label(row_f, f"{sign}${r['amount']:,.2f}", font=FONT_SMALL, fg=color).pack(side="right", padx=8)

# ─── TRANSACTIONS ─────────────────────────────────────────────────────────────
class TransactionsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        # Header + Add button
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=30, pady=(24,0))
        label(hdr, "Transactions", font=FONT_H1).pack(side="left")
        styled_btn(hdr, "+ Add", self._open_add_dialog).pack(side="right", pady=8)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30, pady=12)

        # Table
        table_frame = card_frame(self)
        table_frame.pack(fill="both", expand=True, padx=30, pady=(0,20))

        cols = ("Date", "Type", "Category", "Description", "Amount")
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Budget.Treeview",
                         background=CARD, foreground=TEXT,
                         rowheight=32, fieldbackground=CARD,
                         font=FONT_BODY, borderwidth=0)
        style.configure("Budget.Treeview.Heading",
                         background=PANEL, foreground=SUBTEXT,
                         font=FONT_SMALL, relief="flat")
        style.map("Budget.Treeview", background=[("selected", ACCENT)])

        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                  style="Budget.Treeview", selectmode="browse")
        widths = [90, 80, 130, 260, 100]
        for col, w in zip(cols, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        sb.pack(side="right", fill="y")

        # Delete button
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(fill="x", padx=30, pady=(0,16))
        styled_btn(btn_row, "🗑  Delete Selected", self._delete_selected,
                   color=DANGER, fg=TEXT).pack(side="left")

        self.refresh()

    def refresh(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for r in get_transactions():
            sign = "+" if r["type"] == "income" else "−"
            tag  = r["type"]
            self.tree.insert("", "end",
                iid=str(r["id"]),
                values=(r["date"], r["type"].title(), r["category"],
                        r["description"] or "—", f"{sign}${r['amount']:,.2f}"),
                tags=(tag,))
        self.tree.tag_configure("income",  foreground=ACCENT2)
        self.tree.tag_configure("expense", foreground=DANGER)

    def _open_add_dialog(self):
        type_ = simpledialog.askstring("Add Transaction", "Type (income or expense):", parent=self)
        if not type_ or type_.lower() not in("income", "expense"):
            messagebox.showerror("Invalid", "Please enter either 'income' or 'expense'.")
            return
        amount = simpledialog.askfloat("Add Transaction", "Amount ($):", parent=self, minvalue=0.01)
        if not amount:
            return
        category = simpledialog.askstring("Add Transaction", f"Category\n({', '.join(CATEGORIES)}):", parent=self)
        if not category or category not in CATEGORIES:
            messagebox.showerror("Invalid", f"Please enter a valid category.")
            return
        description = simpledialog.askstring("Add Transaction", "Description (optional):", parent=self)
        date = simpledialog.askstring("Add Transaction", "Date (YYYY-MM-DD):", parent=self, initialvalue=datetime.date.today().isoformat())
        if not date:
            return
        add_transaction(type_.lower(), amount, category, description or "", date)
        self.app.refresh_all()

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Please select a transaction to delete.")
            return
        if messagebox.askyesno("Delete", "Delete this transaction?"):
            delete_transaction(int(sel[0]))
            self.app.refresh_all()

class AddTransactionDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Add Transaction")
        self.geometry("420x400")
        self.configure(bg=PANEL)
        self.resizable(False, False)
        self.grab_set()
        self.focus_force()
        self._build()

    def _build(self):
        pad = {"padx": 24, "pady": 6}

        label(self, "Add Transaction", font=FONT_H2).pack(**pad, anchor="w", pady=(20,4))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24, pady=4)

        # Type
        type_frame = tk.Frame(self, bg=PANEL)
        type_frame.pack(fill="x", **pad)
        label(type_frame, "Type", fg=SUBTEXT, font=FONT_SMALL).pack(anchor="w")
        self.type_var = tk.StringVar(value="expense")
        for val, txt in [("expense","Expense"),("income","Income")]:
            tk.Radiobutton(type_frame, text=txt, variable=self.type_var, value=val,
                           bg=PANEL, fg=TEXT, selectcolor=CARD,
                           activebackground=PANEL, font=FONT_BODY).pack(side="left", padx=8)

        # Amount
        amt_f = tk.Frame(self, bg=PANEL)
        amt_f.pack(fill="x", **pad)
        label(amt_f, "Amount ($)", fg=SUBTEXT, font=FONT_SMALL).pack(anchor="w")
        self.amt_var = tk.StringVar()
        self.amt_entry = tk.Entry(amt_f, textvariable=self.amt_var , bg=CARD, fg=TEXT,
                                  insertbackground=TEXT, relief="flat", font=FONT_BODY)
        self.amt_entry.pack(fill="x", pady=2, ipady=6)
        self.after(150, self.amt_entry.focus_set)

        # Category
        cat_f = tk.Frame(self, bg=PANEL)
        cat_f.pack(fill="x", **pad)
        label(cat_f, "Category", fg=SUBTEXT, font=FONT_SMALL).pack(anchor="w")
        self.cat_var = tk.StringVar(value=CATEGORIES[0])
        ttk.Combobox(cat_f, textvariable=self.cat_var, values=CATEGORIES,
                     state="readonly", font=FONT_BODY).pack(fill="x", pady=2)

        # Description
        desc_f = tk.Frame(self, bg=PANEL)
        desc_f.pack(fill="x", **pad)
        label(desc_f, "Description (optional)", fg=SUBTEXT, font=FONT_SMALL).pack(anchor="w")
        self.desc_var = tk.StringVar()
        tk.Entry(desc_f, textvariable=self.desc_var, bg=CARD, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=FONT_BODY).pack(fill="x", pady=2, ipady=6)

        # Date
        date_f = tk.Frame(self, bg=PANEL)
        date_f.pack(fill="x", **pad)
        label(date_f, "Date (YYYY-MM-DD)", fg=SUBTEXT, font=FONT_SMALL).pack(anchor="w")
        self.date_var = tk.StringVar(value=datetime.date.today().isoformat())
        tk.Entry(date_f, textvariable=self.date_var, bg=CARD, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=FONT_BODY).pack(fill="x", pady=2, ipady=6)

        # Buttons
        btn_row = tk.Frame(self, bg=PANEL)
        btn_row.pack(fill="x", padx=24, pady=16)
        styled_btn(btn_row, "Save", self._save).pack(side="right", padx=(8,0))
        styled_btn(btn_row, "Cancel", self.destroy, color=BORDER, fg=TEXT).pack(side="right")

        self.after(100, lambda: self.amt_var)
        self.after(100, lambda: self.focus_force()) 

    def _save(self):
        try:
            amount = float(self.amt_var.get())
            assert amount > 0
        except:
            messagebox.showerror("Invalid", "Please enter a valid positive amount.")
            return
        try:
            datetime.date.fromisoformat(self.date_var.get())
        except:
            messagebox.showerror("Invalid", "Date must be YYYY-MM-DD.")
            return
        add_transaction(
            self.type_var.get(), amount,
            self.cat_var.get(), self.desc_var.get(),
            self.date_var.get()
        )
        self.app.refresh_all()
        self.destroy()

# ─── GOALS ────────────────────────────────────────────────────────────────────
class GoalsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=30, pady=(24,0))
        label(hdr, "Savings Goals", font=FONT_H1).pack(side="left")
        styled_btn(hdr, "+ New Goal", self._add_goal_dialog).pack(side="right", pady=8)
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30, pady=12)

        self.goals_area = tk.Frame(self, bg=BG)
        self.goals_area.pack(fill="both", expand=True, padx=30)
        self.refresh()

    def refresh(self):
        for w in self.goals_area.winfo_children():
            w.destroy()
        goals = get_goals()
        if not goals:
            label(self.goals_area, "No goals yet. Add one to get started!", fg=SUBTEXT).pack(pady=40)
            return
        for g in goals:
            self._goal_card(g)

    def _goal_card(self, g):
        c = card_frame(self.goals_area)
        c.pack(fill="x", pady=6, ipady=10)

        top = tk.Frame(c, bg=CARD)
        top.pack(fill="x", padx=16, pady=(10,4))
        label(top, g["name"], font=FONT_H2).pack(side="left")
        label(top, f"${g['saved']:,.2f} / ${g['target']:,.2f}", fg=SUBTEXT).pack(side="right")

        # Progress bar
        pct = min(g["saved"] / g["target"], 1.0) if g["target"] else 0
        bar_bg = tk.Frame(c, bg=PANEL, height=10)
        bar_bg.pack(fill="x", padx=16, pady=(0,8))
        bar_bg.update_idletasks()
        fill_w = int(bar_bg.winfo_reqwidth() * pct)

        def draw_bar(event, bg=bar_bg, p=pct):
            w = bg.winfo_width()
            for child in bg.winfo_children():
                child.destroy()
            fill = tk.Frame(bg, bg=ACCENT2 if p < 1 else ACCENT, height=10,
                            width=int(w * p))
            fill.place(x=0, y=0, relheight=1)

        bar_bg.bind("<Configure>", draw_bar)

        label(c, f"{pct*100:.1f}% complete", font=FONT_SMALL, fg=SUBTEXT).pack(anchor="w", padx=16)

        btn_row = tk.Frame(c, bg=CARD)
        btn_row.pack(anchor="e", padx=16, pady=(4,4))
        styled_btn(btn_row, "＋ Add Funds", lambda gid=g["id"]: self._add_funds(gid),
                   color=ACCENT2, fg=BG).pack(side="left", padx=(0,8))
        styled_btn(btn_row, "Delete", lambda gid=g["id"]: self._delete_goal(gid),
                   color=DANGER, fg=TEXT).pack(side="left")

    def _add_goal_dialog(self):
        name = simpledialog.askstring("New Goal", "Goal name:", parent=self)
        if not name: return
        target = simpledialog.askfloat("New Goal", "Target amount ($):", parent=self, minvalue=1)
        if not target: return
        add_goal(name, target)
        self.refresh()

    def _add_funds(self, gid):
        amount = simpledialog.askfloat("Add Funds", "Amount to add ($):", parent=self, minvalue=0.01)
        if not amount: return
        update_goal_saved(gid, amount)
        self.refresh()

    def _delete_goal(self, gid):
        if messagebox.askyesno("Delete", "Delete this goal?"):
            delete_goal(gid)
            self.refresh()

# ─── REPORTS ──────────────────────────────────────────────────────────────────
class ReportsPage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._build()

    def _build(self):
        now = datetime.date.today()
        self.year = now.year

        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=30, pady=(24,0))
        label(hdr, "Monthly Reports", font=FONT_H1).pack(side="left")

        ctrl = tk.Frame(hdr, bg=BG)
        ctrl.pack(side="right", pady=8)
        label(ctrl, "Year:", fg=SUBTEXT).pack(side="left")
        self.year_var = tk.StringVar(value=str(self.year))
        year_spin = tk.Spinbox(ctrl, from_=2020, to=2099, textvariable=self.year_var,
                               width=6, bg=CARD, fg=TEXT, buttonbackground=PANEL,
                               font=FONT_BODY, relief="flat",
                               command=self.refresh)
        year_spin.pack(side="left", padx=8, ipady=4)
        styled_btn(ctrl, "Refresh", self.refresh).pack(side="left")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=30, pady=12)

        self.chart_area = tk.Frame(self, bg=BG)
        self.chart_area.pack(fill="both", expand=True, padx=30, pady=(0,20))

        self.refresh()

    def refresh(self):
        for w in self.chart_area.winfo_children():
            w.destroy()
        try:
            year = int(self.year_var.get())
        except:
            year = datetime.date.today().year

        months = list(range(1, 13))
        incomes   = []
        expenses  = []
        for m in months:
            inc, exp, _ = monthly_summary(m, year)
            incomes.append(inc)
            expenses.append(exp)

        fig = Figure(figsize=(9, 4.5), dpi=90, facecolor=BG)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(PANEL)

        x = list(range(12))
        w = 0.35
        bars_inc = ax.bar([i - w/2 for i in x], incomes,  width=w, color=ACCENT2, label="Income",   zorder=3)
        bars_exp = ax.bar([i + w/2 for i in x], expenses, width=w, color=DANGER,  label="Expenses", zorder=3)

        ax.set_xticks(x)
        ax.set_xticklabels([calendar.month_abbr[m] for m in months], color=SUBTEXT, fontsize=9)
        ax.tick_params(colors=SUBTEXT, which="both")
        ax.yaxis.label.set_color(SUBTEXT)
        ax.spines[:].set_color(BORDER)
        ax.grid(axis="y", color=BORDER, linestyle="--", alpha=0.5, zorder=0)
        ax.set_ylabel("Amount ($)", color=SUBTEXT)
        ax.set_title(f"Income vs Expenses — {year}", color=TEXT, fontsize=13, pad=12)
        ax.legend(facecolor=PANEL, edgecolor=BORDER, labelcolor=TEXT)

        fig.tight_layout(pad=1.5)
        canvas = FigureCanvasTkAgg(fig, master=self.chart_area)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        # Monthly net table
        tbl_frame = card_frame(self.chart_area)
        tbl_frame.pack(fill="x", pady=(16,0))
        cols = ["Month", "Income", "Expenses", "Net"]
        hdr_row = tk.Frame(tbl_frame, bg=PANEL)
        hdr_row.pack(fill="x")
        for c in cols:
            label(hdr_row, c, font=FONT_SMALL, fg=SUBTEXT).pack(side="left", expand=True, padx=8, pady=6)

        for i, m in enumerate(months):
            net = incomes[i] - expenses[i]
            row_bg = CARD if i % 2 == 0 else PANEL
            row_f = tk.Frame(tbl_frame, bg=row_bg)
            row_f.pack(fill="x")
            net_color = ACCENT2 if net >= 0 else DANGER
        label(row_f, calendar.month_abbr[m], fg=TEXT, font=FONT_SMALL).pack(side="left", expand=True, padx=8, pady=5)
        label(row_f, f"${incomes[i]:,.2f}", fg=ACCENT2, font=FONT_SMALL).pack(side="left", expand=True, padx=8)
        label(row_f, f"${expenses[i]:,.2f}", fg=DANGER, font=FONT_SMALL).pack(side="left", expand=True, padx=8)
        label(row_f, f"${net:,.2f}", fg=net_color, font=FONT_SMALL).pack(side="left", expand=True, padx=8)

# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = BudgetApp()
    app.mainloop()
