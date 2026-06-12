import sys
import os
import json
import uuid
import shutil
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from PyQt6.QtWidgets import (
    QApplication, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QStackedWidget, QInputDialog, QComboBox, QFrame, QFileDialog
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

# ------------------- Configurações -------------------
DATA_DIR = os.path.join(os.path.expanduser("~"), ".dlicia_app")
STOCK_FILE = os.path.join(DATA_DIR, "stock.json")
SALES_FILE = os.path.join(DATA_DIR, "sales.json")
COSTS_FILE = os.path.join(DATA_DIR, "costs.json")
FINANCES_FILE = os.path.join(DATA_DIR, "finances.json")
os.makedirs(DATA_DIR, exist_ok=True)

LOGIN_USER = "Admin"
LOGIN_PASS = "admin"

# ------------------- Utilitários -------------------
def money(v):
    return f"R$ {Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}"

def parse_money(text):
    if text is None:
        return Decimal("0.00")
    t = str(text).strip()
    t = t.replace("R$", "").replace("r$", "").strip()
    t = t.replace(".", "").replace(",", ".") if "," in t and "." in t and t.find(",") > t.find(".") else t.replace(",", ".")
    t = re.sub(r"[^\d\.\-]", "", t)
    if t == "" or t == "-" or t == ".":
        return Decimal("0.00")
    try:
        return Decimal(t)
    except InvalidOperation:
        return Decimal("0.00")

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return default
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ------------------- Modelo -------------------
class Dlicia:
    def __init__(self):
        self.stock = load_json(STOCK_FILE, [])
        self.sales = load_json(SALES_FILE, [])
        self.costs = load_json(COSTS_FILE, [])
        self.finances = load_json(FINANCES_FILE, {})
        self.finances.setdefault("cash", 0.0)
        self.finances.setdefault("reserve_purchases", 0.0)
        self.finances.setdefault("reserve_savings", 0.0)
        self.finances.setdefault("logo_path", "")
        self.save()

    def save(self):
        save_json(STOCK_FILE, self.stock)
        save_json(SALES_FILE, self.sales)
        save_json(COSTS_FILE, self.costs)
        save_json(FINANCES_FILE, self.finances)

    # ----- Estoque -----
    def add_product(self, name, price, qty):
        pid = str(uuid.uuid4())
        self.stock.append({"id": pid, "name": name, "price": float(price), "qty": int(qty)})
        self.save()

    def delete_product(self, product_id):
        self.stock = [p for p in self.stock if p["id"] != product_id]
        self.save()

    # ----- Vendas -----
    def sell(self, product_id, qty):
        product = next((p for p in self.stock if p["id"] == product_id), None)
        if not product or qty > product["qty"]:
            return False
        total = product["price"] * qty
        product["qty"] -= qty
        sale_id = str(uuid.uuid4())
        self.sales.append({
            "id": sale_id, "product_id": product_id, "name": product["name"],
            "qty": qty, "total": float(total), "date": datetime.now().isoformat()
        })
        self.finances["cash"] += total * 0.4
        self.finances["reserve_purchases"] += total * 0.4
        self.finances["reserve_savings"] += total * 0.2
        self.save()
        return True

    def delete_sale(self, sale_id):
        sale = next((s for s in self.sales if s["id"] == sale_id), None)
        if sale:
            self.finances["cash"] -= sale["total"] * 0.4
            self.finances["reserve_purchases"] -= sale["total"] * 0.4
            self.finances["reserve_savings"] -= sale["total"] * 0.2
            prod = next((p for p in self.stock if p["id"] == sale["product_id"]), None)
            if prod:
                prod["qty"] += sale["qty"]
            self.sales = [s for s in self.sales if s["id"] != sale_id]
            self.save()

    # ----- Custos -----
    def add_cost(self, amount, desc="Custo"):
        cost_id = str(uuid.uuid4())
        self.costs.append({"id": cost_id, "amount": float(amount), "desc": desc, "date": datetime.now().isoformat()})
        # Subtrai apenas da reserva de compras
        self.finances["reserve_purchases"] -= float(amount)
        self.save()

    def delete_cost(self, cost_id):
        cost = next((c for c in self.costs if c["id"] == cost_id), None)
        if cost:
            self.finances["cash"] += cost["amount"]
            self.finances["reserve_purchases"] += cost["amount"]
            self.costs = [c for c in self.costs if c["id"] != cost_id]
            self.save()

    def adjust_cost_amount(self, cost_id, new_amount):
        cost = next((c for c in self.costs if c["id"] == cost_id), None)
        if not cost:
            return
        old = Decimal(str(cost["amount"]))
        new = Decimal(str(new_amount))
        diff = new - old
        self.finances["cash"] -= float(diff)
        self.finances["reserve_purchases"] -= float(diff)
        cost["amount"] = float(new)
        cost["date"] = datetime.now().isoformat()
        self.save()

    # ----- Reservas líquidas -----
    def get_reserve_purchases_liquid(self):
        total_costs = sum(c["amount"] for c in self.costs)
        return self.finances["reserve_purchases"] - total_costs

    # ----- Reset Finanças -----
    def reset_cash(self):
        self.finances["cash"] = 0.0
        self.save()

    def reset_reserve_purchases(self):
        self.finances["reserve_purchases"] = 0.0
        self.save()

    def reset_reserve_savings(self):
        self.finances["reserve_savings"] = 0.0
        self.save()

    # ----- Logo -----
    def set_logo(self, src_path):
        if not src_path or not os.path.exists(src_path):
            return
        ext = os.path.splitext(src_path)[1]
        dest = os.path.join(DATA_DIR, f"logo{ext}")
        try:
            shutil.copy(src_path, dest)
            self.finances["logo_path"] = dest
            self.save()
        except Exception:
            self.finances["logo_path"] = src_path
            self.save()

    def get_logo(self):
        return self.finances.get("logo_path", "")

# ------------------- Interface -------------------
class DliciaApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("D'Licia - Controle de Trufas")
        self.setMinimumSize(980, 720)
        self.model = Dlicia()
        self.stack = QStackedWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.stack)
        self.setLayout(main_layout)
        # flag para suprimir sinais quando atualizo a tabela programaticamente
        self.suppress_item_changed = False
        # rastrear tabelas que têm edição habilitada
        self.editable_tables = set()
        self.init_login()
        self.init_main_ui()
        self.stack.setCurrentWidget(self.login_widget)

    # ---------------- Login ----------------
    def init_login(self):
        self.login_widget = QWidget()
        self.login_widget.setMinimumSize(480, 320)
        self.login_widget.setStyleSheet("background-color:#fff7f7; border-radius:12px;")
        layout = QVBoxLayout(); layout.setContentsMargins(60,30,60,30); layout.setSpacing(12)
        self.login_widget.setLayout(layout)

        # logo area
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setFixedHeight(150)
        self.logo_label.setStyleSheet("border:1px dashed #d3a; padding:6px;")
        layout.addWidget(self.logo_label)
        self.load_logo()

        btn_logo = QPushButton("Selecionar Logo")
        btn_logo.setStyleSheet("background-color:#ffd6d6; height:34px; border-radius:6px;")
        btn_logo.clicked.connect(self.select_logo)
        layout.addWidget(btn_logo)

        logo = QLabel("D'Licia")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size:42px; color:#b22222; font-weight:700;")
        subtitle = QLabel("Controle simples de trufas 🍫")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color:#8b0000; font-size:14px;")

        self.login_user = QLineEdit(); self.login_user.setPlaceholderText("Usuário")
        self.login_user.setStyleSheet("height:36px; font-size:16px; padding:4px;")
        self.login_pass = QLineEdit(); self.login_pass.setPlaceholderText("Senha"); self.login_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.login_pass.setStyleSheet("height:36px; font-size:16px; padding:4px;")
        btn_login = QPushButton("Entrar"); btn_login.setStyleSheet(
            "background-color:#ff6f6f; color:white; font-weight:700; height:40px; font-size:16px; border-radius:8px;"
        )
        btn_login.clicked.connect(self.check_login)

        layout.addWidget(logo)
        layout.addWidget(subtitle)
        layout.addStretch()
        layout.addWidget(self.login_user)
        layout.addWidget(self.login_pass)
        layout.addWidget(btn_login)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.stack.addWidget(self.login_widget)

    def select_logo(self):
        file, _ = QFileDialog.getOpenFileName(self, "Selecionar Logo", "", "Imagens (*.png *.jpg *.jpeg *.bmp *.gif)")
        if file:
            self.model.set_logo(file)
            self.load_logo()
            QMessageBox.information(self, "Logo", "Logo selecionado e salvo.")

    def load_logo(self):
        logo_path = self.model.get_logo()
        if logo_path and os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            self.logo_label.setPixmap(pixmap.scaled(220, 140, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.logo_label.setText("[Logo não definido]")

    def check_login(self):
        if self.login_user.text() == LOGIN_USER and self.login_pass.text() == LOGIN_PASS:
            self.stack.setCurrentWidget(self.main_widget)
        else:
            QMessageBox.warning(self, "Erro", "Usuário ou senha incorretos")

    # ---------------- UI Principal ----------------
    def init_main_ui(self):
        self.main_widget = QWidget()
        layout = QVBoxLayout(); layout.setContentsMargins(12,12,12,12)
        self.main_widget.setLayout(layout)
        self.stack.addWidget(self.main_widget)

        header = QLabel("<h1 style='color:#b22222'>D'Licia - Controle de Trufas</h1>")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("margin-bottom:6px;")
        subtitle = QLabel("Simples, visual e seguro — perfeito para aprender e controlar vendas.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color:#7a2a2a; margin-bottom:12px;")

        layout.addWidget(header)
        layout.addWidget(subtitle)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 2px solid #ffd6d6; border-radius:10px; padding:8px; background:#fffaf9; }
            QTabBar::tab { background: #ffecec; padding:12px; font-size:15px; border-radius:6px; margin-right:6px; }
            QTabBar::tab:selected { background: #ff6f6f; color: white; font-weight:700; }
        """)
        layout.addWidget(self.tabs)

        # Abas
        self.tab_stock = QWidget(); self.tabs.addTab(self.tab_stock, "Estoque"); self.init_tab_stock()
        self.tab_sales = QWidget(); self.tabs.addTab(self.tab_sales, "Vendas"); self.init_tab_sales()
        self.tab_cost = QWidget(); self.tabs.addTab(self.tab_cost, "Custos"); self.init_tab_cost()
        self.tab_purchase = QWidget(); self.tabs.addTab(self.tab_purchase, "Reserva Compras"); self.init_tab_purchase()
        self.tab_cash = QWidget(); self.tabs.addTab(self.tab_cash, "Meu Dinheiro"); self.init_tab_cash()
        self.tab_savings = QWidget(); self.tabs.addTab(self.tab_savings, "Minha Poupança"); self.init_tab_savings()

        # Footer quick help
        help_frame = QFrame(); help_layout = QHBoxLayout(); help_frame.setLayout(help_layout)
        hint = QLabel("Dica: clique nas tabelas para selecionar itens. Use nomes simples para os produtos.")
        hint.setStyleSheet("color:#5f2b2b;")
        help_layout.addWidget(hint)
        layout.addWidget(help_frame)

        self.refresh_all()

    # ---------------- Aba Estoque ----------------
    def init_tab_stock(self):
        layout = QVBoxLayout(); self.tab_stock.setLayout(layout)
        self.stock_table = QTableWidget(0,3)
        self.stock_table.setHorizontalHeaderLabels(["Nome","Preço","Qtd"])
        self.stock_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stock_table.setStyleSheet("font-size:14px;")
        self.stock_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # conectar sinal de mudança de item (usado quando edição está habilitada)
        self.stock_table.itemChanged.connect(lambda item: self.on_item_changed(self.stock_table, item))
        layout.addWidget(self.stock_table)

        form = QHBoxLayout()
        self.stock_name = QLineEdit(); self.stock_name.setPlaceholderText("Nome (ex: Trufa Brigadeiro)")
        self.stock_price = QDoubleSpinBox(); self.stock_price.setPrefix("R$ "); self.stock_price.setMaximum(100000); self.stock_price.setDecimals(2)
        self.stock_qty = QSpinBox(); self.stock_qty.setMaximum(100000)

        btn_add = QPushButton("Adicionar"); btn_add.clicked.connect(self.add_stock)
        btn_add.setStyleSheet("background-color:#ff9b9b; font-weight:700; height:36px; border-radius:6px;")
        btn_del = QPushButton("Excluir"); btn_del.clicked.connect(self.delete_stock)
        btn_del.setStyleSheet("background-color:#ff4d4d; color:white; font-weight:700; height:36px; border-radius:6px;")
        btn_edit = QPushButton("Editar"); btn_edit.setStyleSheet("background-color:#ffa500; color:white; font-weight:700; height:36px; border-radius:6px;")
        btn_edit.clicked.connect(lambda: self.enable_editing(self.stock_table))

        form.addWidget(self.stock_name); form.addWidget(self.stock_price); form.addWidget(self.stock_qty)
        form.addWidget(btn_add); form.addWidget(btn_del); form.addWidget(btn_edit)
        layout.addLayout(form)

    def refresh_stock(self):
        self.suppress_item_changed = True
        self.stock_table.setRowCount(0)
        for p in self.model.stock:
            r = self.stock_table.rowCount()
            self.stock_table.insertRow(r)
            item_name = QTableWidgetItem(p["name"])
            item_name.setData(Qt.ItemDataRole.UserRole, p["id"])
            self.stock_table.setItem(r,0,item_name)
            self.stock_table.setItem(r,1,QTableWidgetItem(money(p["price"])))
            self.stock_table.setItem(r,2,QTableWidgetItem(str(p["qty"])))
        self.suppress_item_changed = False

    def add_stock(self):
        name = self.stock_name.text().strip()
        price = self.stock_price.value()
        qty = self.stock_qty.value()
        if not name:
            QMessageBox.warning(self, "Atenção", "Digite um nome para o produto.")
            return
        if price <= 0 or qty <= 0:
            QMessageBox.warning(self, "Atenção", "Preço e quantidade devem ser maiores que zero.")
            return
        self.model.add_product(name, price, qty)
        self.stock_name.clear(); self.stock_price.setValue(0); self.stock_qty.setValue(0)
        self.refresh_all()

    def delete_stock(self):
        row = self.stock_table.currentRow()
        if row < 0:
            return
        pid = self.stock_table.item(row,0).data(Qt.ItemDataRole.UserRole)
        confirm = QMessageBox.question(self, "Confirmar", "Excluir produto selecionado?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.model.delete_product(pid)
            self.refresh_all()

    # ---------------- Aba Vendas ----------------
    def init_tab_sales(self):
        layout = QVBoxLayout(); self.tab_sales.setLayout(layout)
        form = QHBoxLayout()
        self.sale_product_combo = QComboBox()
        self.refresh_sale_combo()
        self.sale_qty = QSpinBox(); self.sale_qty.setMaximum(100000)
        btn_sell = QPushButton("Vender"); btn_sell.clicked.connect(self.add_sale)
        btn_del_sale = QPushButton("Excluir Venda"); btn_del_sale.clicked.connect(self.delete_sale)
        btn_edit_sale = QPushButton("Editar"); btn_edit_sale.clicked.connect(lambda: self.enable_editing(self.sales_table))
        btn_sell.setStyleSheet("background-color:#ff9b9b; font-weight:700; height:36px; border-radius:6px;")
        btn_del_sale.setStyleSheet("background-color:#ff8b8b; height:36px; border-radius:6px;")
        btn_edit_sale.setStyleSheet("background-color:#ffa500; color:white; font-weight:700; height:36px; border-radius:6px;")
        form.addWidget(self.sale_product_combo); form.addWidget(self.sale_qty)
        form.addWidget(btn_sell); form.addWidget(btn_del_sale); form.addWidget(btn_edit_sale)
        layout.addLayout(form)

        self.sales_table = QTableWidget(0,4)
        self.sales_table.setHorizontalHeaderLabels(["Produto","Qtd","Total","Data"])
        self.sales_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.sales_table.setStyleSheet("font-size:14px;")
        self.sales_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # conectar sinal de mudança
        self.sales_table.itemChanged.connect(lambda item: self.on_item_changed(self.sales_table, item))
        layout.addWidget(self.sales_table)

    def refresh_sale_combo(self):
        self.sale_product_combo.clear()
        for p in self.model.stock:
            if p["qty"] > 0:
                self.sale_product_combo.addItem(f"{p['name']} (Q:{p['qty']})", p["id"])
        if self.sale_product_combo.count() == 0:
            self.sale_product_combo.addItem("Sem produtos disponíveis", None)

    def refresh_sales(self):
        self.suppress_item_changed = True
        self.sales_table.setRowCount(0)
        for s in reversed(self.model.sales):
            r = self.sales_table.rowCount()
            self.sales_table.insertRow(r)
            item_name = QTableWidgetItem(s["name"])
            item_name.setData(Qt.ItemDataRole.UserRole, s["id"])
            self.sales_table.setItem(r,0,item_name)
            self.sales_table.setItem(r,1,QTableWidgetItem(str(s["qty"])))
            self.sales_table.setItem(r,2,QTableWidgetItem(money(s["total"])))
            try:
                formatted = datetime.fromisoformat(s["date"]).strftime("%d/%m/%Y %H:%M")
            except Exception:
                formatted = s.get("date", "")
            self.sales_table.setItem(r,3,QTableWidgetItem(formatted))
        self.suppress_item_changed = False

    def add_sale(self):
        pid = self.sale_product_combo.currentData()
        if not pid:
            QMessageBox.warning(self, "Erro", "Nenhum produto selecionado.")
            return
        qty = self.sale_qty.value()
        if qty <= 0:
            QMessageBox.warning(self, "Erro", "Quantidade deve ser maior que zero.")
            return
        success = self.model.sell(pid, qty)
        if success:
            self.sale_qty.setValue(0)
            self.refresh_all()
        else:
            QMessageBox.warning(self, "Erro", "Quantidade insuficiente no estoque.")

    def delete_sale(self):
        row = self.sales_table.currentRow()
        if row < 0:
            return
        sale_id = self.sales_table.item(row,0).data(Qt.ItemDataRole.UserRole)
        confirm = QMessageBox.question(self, "Confirmar", "Excluir venda selecionada? (estoque será restituído)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.model.delete_sale(sale_id)
            self.refresh_all()

    # ---------------- Aba Custos ----------------
    def init_tab_cost(self):
        layout = QVBoxLayout(); self.tab_cost.setLayout(layout)
        form = QHBoxLayout()
        self.cost_desc = QLineEdit(); self.cost_desc.setPlaceholderText("Descrição (ex: Ingredientes)")
        self.cost_amount = QDoubleSpinBox(); self.cost_amount.setPrefix("R$ "); self.cost_amount.setMaximum(1000000); self.cost_amount.setDecimals(2)
        btn_add_cost = QPushButton("Adicionar Custo"); btn_add_cost.clicked.connect(self.add_cost)
        btn_del_cost = QPushButton("Excluir Custo"); btn_del_cost.clicked.connect(self.delete_cost)
        btn_edit_cost = QPushButton("Editar"); btn_edit_cost.clicked.connect(lambda: self.enable_editing(self.cost_table))
        btn_add_cost.setStyleSheet("background-color:#ffd1d1; height:36px; border-radius:6px;")
        btn_del_cost.setStyleSheet("background-color:#ffb3b3; height:36px; border-radius:6px;")
        btn_edit_cost.setStyleSheet("background-color:#ffa500; color:white; height:36px; border-radius:6px;")
        form.addWidget(self.cost_desc); form.addWidget(self.cost_amount); form.addWidget(btn_add_cost); form.addWidget(btn_del_cost); form.addWidget(btn_edit_cost)
        layout.addLayout(form)

        self.cost_table = QTableWidget(0,3)
        self.cost_table.setHorizontalHeaderLabels(["Descrição","Valor","Data"])
        self.cost_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.cost_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # conectar sinal de mudança
        self.cost_table.itemChanged.connect(lambda item: self.on_item_changed(self.cost_table, item))
        layout.addWidget(self.cost_table)

    def refresh_costs(self):
        self.suppress_item_changed = True
        self.cost_table.setRowCount(0)
        for c in reversed(self.model.costs):
            r = self.cost_table.rowCount()
            self.cost_table.insertRow(r)
            item = QTableWidgetItem(c["desc"])
            item.setData(Qt.ItemDataRole.UserRole, c["id"])
            self.cost_table.setItem(r,0,item)
            self.cost_table.setItem(r,1,QTableWidgetItem(money(c["amount"])))
            try:
                formatted = datetime.fromisoformat(c["date"]).strftime("%d/%m/%Y %H:%M")
            except:
                formatted = c.get("date","")
            self.cost_table.setItem(r,2,QTableWidgetItem(formatted))
        self.suppress_item_changed = False

    def add_cost(self):
        desc = self.cost_desc.text().strip()
        amt = self.cost_amount.value()
        if not desc:
            desc = "Custo"
        if amt <= 0:
            QMessageBox.warning(self,"Erro","Valor deve ser maior que zero")
            return
        self.model.add_cost(amt,desc)
        self.cost_desc.clear(); self.cost_amount.setValue(0)
        self.refresh_all()

    def delete_cost(self):
        row = self.cost_table.currentRow()
        if row < 0:
            return
        cid = self.cost_table.item(row,0).data(Qt.ItemDataRole.UserRole)
        confirm = QMessageBox.question(self,"Confirmar","Excluir custo?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.model.delete_cost(cid)
            self.refresh_all()

    # ---------------- Aba Reserva Compras ----------------
    def init_tab_purchase(self):
        layout = QVBoxLayout(); self.tab_purchase.setLayout(layout)
        header = QLabel("Reserva para compras (ingredientes, embalagens...)")
        header.setStyleSheet("font-size:16px; font-weight:700; color:#6b2a2a;")
        layout.addWidget(header)

        self.lbl_purchase = QLabel(); self.lbl_purchase.setStyleSheet("font-size:18px; font-weight:700;")
        layout.addWidget(self.lbl_purchase)

        self.purchase_history = QTableWidget(0,2)
        self.purchase_history.setHorizontalHeaderLabels(["Tipo","Valor"])
        self.purchase_history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.purchase_history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(QLabel("Resumo (últimas operações relacionadas à reserva):"))
        layout.addWidget(self.purchase_history)

        # botão zerar reserva (apenas adição)
        btn_reset_purchase = QPushButton("Zerar Reserva de Compras")
        btn_reset_purchase.setStyleSheet("background-color:#ffb3b3; height:36px; border-radius:6px;")
        btn_reset_purchase.clicked.connect(self.reset_reserve_purchases)
        layout.addWidget(btn_reset_purchase)

    # ---------------- Aba Caixa ----------------
    def init_tab_cash(self):
        layout = QVBoxLayout(); self.tab_cash.setLayout(layout)
        self.lbl_cash = QLabel(); self.lbl_cash.setStyleSheet("font-size:22px; font-weight:700; color:#b22222;")
        layout.addWidget(self.lbl_cash)

        # botão zerar caixa
        btn_reset_cash = QPushButton("Zerar Meu Dinheiro")
        btn_reset_cash.setStyleSheet("background-color:#ffb3b3; height:36px; border-radius:6px;")
        btn_reset_cash.clicked.connect(self.reset_cash)
        layout.addWidget(btn_reset_cash)

    # ---------------- Aba Poupança ----------------
    def init_tab_savings(self):
        layout = QVBoxLayout(); self.tab_savings.setLayout(layout)
        self.lbl_savings = QLabel(); self.lbl_savings.setStyleSheet("font-size:22px; font-weight:700; color:#b22222;")
        layout.addWidget(self.lbl_savings)

        # botão zerar poupança
        btn_reset_savings = QPushButton("Zerar Minha Poupança")
        btn_reset_savings.setStyleSheet("background-color:#ffb3b3; height:36px; border-radius:6px;")
        btn_reset_savings.clicked.connect(self.reset_reserve_savings)
        layout.addWidget(btn_reset_savings)

    # ---------------- Funções Comuns ----------------
    def refresh_all(self):
        self.refresh_stock(); self.refresh_sale_combo(); self.refresh_sales(); self.refresh_costs()
        self.lbl_cash.setText(f"Dinheiro disponível: {money(self.model.finances['cash'])}")
        self.lbl_purchase.setText(f"Reserva para compras: {money(self.model.finances['reserve_purchases'])}")
        self.lbl_savings.setText(f"Poupança: {money(self.model.finances['reserve_savings'])}")
        self.refresh_purchase_history()

    def refresh_purchase_history(self):
        self.purchase_history.setRowCount(0)

        # Valor da reserva para compras (mesmo que lbl_purchase)
        valor_reserva = self.model.finances['reserve_purchases']

        # Inserir linha na tabela
        r = self.purchase_history.rowCount()
        self.purchase_history.insertRow(r)
        self.purchase_history.setItem(r, 0, QTableWidgetItem("Venda → Reserva"))
        self.purchase_history.setItem(r, 1, QTableWidgetItem(money(valor_reserva)))

    def enable_editing(self, table: QTableWidget):
        # pede senha admin antes de habilitar edição
        passwd, ok = QInputDialog.getText(self, "Senha Admin", "Digite a senha do administrador:", QLineEdit.EchoMode.Password)
        if ok and passwd == LOGIN_PASS:
            table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
            self.editable_tables.add(table)
            QMessageBox.information(self, "Editar", "Edição habilitada! As alterações serão salvas automaticamente.")
        else:
            QMessageBox.warning(self, "Erro", "Senha incorreta.")

    def on_item_changed(self, table: QTableWidget, item: QTableWidgetItem):
        """Handler geral para mudanças em tabelas que foram habilitadas para edição.
           Salva automaticamente e atualiza o modelo e saldos conforme necessário.
        """
        if self.suppress_item_changed:
            return  # mudanças programáticas não devem disparar lógica
        if table not in self.editable_tables:
            return  # somente salvar quando a edição foi autorizada

        row = item.row()
        col = item.column()
        # identificar qual tabela é
        if table is self.stock_table:
            # col 0: nome, col1: preço (formatado), col2: qty
            pid = self.stock_table.item(row,0).data(Qt.ItemDataRole.UserRole)
            product = next((p for p in self.model.stock if p["id"] == pid), None)
            if not product:
                return
            try:
                if col == 0:
                    # nome
                    product["name"] = item.text().strip() or product["name"]
                elif col == 1:
                    # preço - parsear
                    v = parse_money(item.text())
                    product["price"] = float(v)
                elif col == 2:
                    # quantidade
                    try:
                        q = int(re.sub(r"[^\d\-]", "", item.text() or "0"))
                        if q < 0:
                            q = 0
                        product["qty"] = q
                    except Exception:
                        pass
                # salvar e atualizar visual
                self.model.save()
                self.refresh_all()
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Falha ao atualizar produto: {e}")

        elif table is self.cost_table:
            # col0: desc, col1: valor, col2: data (data será atualizada automaticamente)
            cid = self.cost_table.item(row,0).data(Qt.ItemDataRole.UserRole)
            cost = next((c for c in self.model.costs if c["id"] == cid), None)
            if not cost:
                return
            if col == 0:
                cost["desc"] = item.text().strip() or cost["desc"]
                cost["date"] = datetime.now().isoformat()
                self.model.save()
                self.refresh_all()
            elif col == 1:
                # ajustar valor -> atualizar finanças proporcionalmente
                new_val = parse_money(item.text())
                try:
                    self.model.adjust_cost_amount(cid, float(new_val))
                    self.refresh_all()
                except Exception as e:
                    QMessageBox.warning(self, "Erro", f"Falha ao ajustar custo: {e}")

        elif table is self.sales_table:
            # col0: nome (não altera finanças), col1: qty (é preciso ajustar estoque e finanças), col2: total (ajusta finanças)
            sid = self.sales_table.item(row,0).data(Qt.ItemDataRole.UserRole)
            sale = next((s for s in self.model.sales if s["id"] == sid), None)
            if not sale:
                return
            try:
                if col == 0:
                    sale["name"] = item.text().strip() or sale["name"]
                    sale["date"] = datetime.now().isoformat()
                    self.model.save()
                    self.refresh_all()
                elif col == 1:
                    # alteração na quantidade: precisamos verificar estoque e ajustar
                    new_qty = int(re.sub(r"[^\d\-]", "", item.text() or "0"))
                    if new_qty < 0:
                        new_qty = 0
                    old_qty = int(sale["qty"])
                    delta_qty = new_qty - old_qty
                    prod = next((p for p in self.model.stock if p["id"] == sale["product_id"]), None)
                    if delta_qty > 0:
                        # estamos aumentando a venda -> devemos retirar do estoque
                        if not prod or prod["qty"] < delta_qty:
                            QMessageBox.warning(self, "Erro", "Estoque insuficiente para aumentar essa venda. Operação cancelada.")
                            self.refresh_all()
                            return
                        prod["qty"] -= delta_qty
                    elif delta_qty < 0:
                        # diminuindo venda -> devolver ao estoque
                        if prod:
                            prod["qty"] += (-delta_qty)
                    # ajustar total proporcionalmente se preço do produto definido
                    price = prod["price"] if prod else (sale["total"] / old_qty if old_qty else 0)
                    new_total = float(Decimal(str(price)) * Decimal(str(new_qty)))
                    delta_total = Decimal(str(new_total)) - Decimal(str(sale["total"]))
                    # aplicar diferença nas finanças (mesma regra: 40/40/20)
                    self.model.finances["cash"] += float(delta_total) * 0.4
                    self.model.finances["reserve_purchases"] += float(delta_total) * 0.4
                    self.model.finances["reserve_savings"] += float(delta_total) * 0.2
                    sale["qty"] = new_qty
                    sale["total"] = float(new_total)
                    sale["date"] = datetime.now().isoformat()
                    self.model.save()
                    self.refresh_all()
                elif col == 2:
                    # alteração no total: ajustar finanças conforme diferença
                    new_total = parse_money(item.text())
                    old_total = Decimal(str(sale["total"]))
                    diff = Decimal(str(new_total)) - old_total
                    self.model.finances["cash"] += float(diff) * 0.4
                    self.model.finances["reserve_purchases"] += float(diff) * 0.4
                    self.model.finances["reserve_savings"] += float(diff) * 0.2
                    sale["total"] = float(new_total)
                    sale["date"] = datetime.now().isoformat()
                    self.model.save()
                    self.refresh_all()
            except Exception as e:
                QMessageBox.warning(self, "Erro", f"Falha ao atualizar venda: {e}")
                self.refresh_all()

    # ---------------- Reset actions ----------------
    def reset_reserve_purchases(self):
        confirm = QMessageBox.question(self, "Confirmar", "Deseja zerar a Reserva de Compras?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.model.reset_reserve_purchases()
            self.refresh_all()
            QMessageBox.information(self, "Sucesso", "Reserva de Compras zerada.")

    def reset_cash(self):
        confirm = QMessageBox.question(self, "Confirmar", "Deseja zerar o Meu Dinheiro (caixa)?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.model.reset_cash()
            self.refresh_all()
            QMessageBox.information(self, "Sucesso", "Meu Dinheiro zerado.")

    def reset_reserve_savings(self):
        confirm = QMessageBox.question(self, "Confirmar", "Deseja zerar a Minha Poupança?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self.model.reset_reserve_savings()
            self.refresh_all()
            QMessageBox.information(self, "Sucesso", "Minha Poupança zerada.")

# ------------------- Executar -------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DliciaApp()
    w.show()
    sys.exit(app.exec())
