# Copyright (c) 2025, Jide (lajidey) and other Oasyx Developers and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import CombineDatetime, Sum
from frappe.utils import cint, flt, get_datetime

from erpnext.stock.doctype.inventory_dimension.inventory_dimension import get_inventory_dimensions
from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import get_stock_balance_for
from erpnext.stock.doctype.warehouse.warehouse import apply_warehouse_filter
from erpnext.stock.utils import (
	update_included_uom_in_report,
)


def execute(filters: dict | None = None):
	"""Return columns and data for the report.

	This is the main entry point for the report. It accepts the filters as a
	dictionary and should return columns and data. It is called by the framework
	every time the report is refreshed or a filter is updated.
	"""
	""" columns = get_columns()
	data = get_data() """

	include_uom = filters.get("include_uom")
	columns = get_columns(filters)
	items = get_items(filters)
	sl_entries = get_stock_ledger_entries(filters, items)
	item_details = get_item_details(items, sl_entries, include_uom)

	opening_row = get_opening_balance(filters, columns, sl_entries)

	precision = cint(frappe.db.get_single_value("System Settings", "float_precision"))

	data = []
	conversion_factors = []
	if opening_row:
		data.append(opening_row)
		conversion_factors.append(0)

	actual_qty = stock_value = 0
	if opening_row:
		actual_qty = opening_row.get("qty_after_transaction")
		stock_value = opening_row.get("stock_value")

	for sle in sl_entries:
		item_detail = item_details[sle.item_code]

		sle.update(item_detail)

		sle.update({"in_qty": max(sle.actual_qty, 0), "out_qty": min(sle.actual_qty, 0)})

		if sle.actual_qty:
			sle["in_out_rate"] = flt(sle.stock_value_difference / sle.actual_qty, precision)

		elif sle.voucher_type == "Stock Reconciliation":
			sle["in_out_rate"] = sle.valuation_rate

		data.append(sle)

		if include_uom:
			conversion_factors.append(item_detail.conversion_factor)

	update_included_uom_in_report(columns, data, include_uom, conversion_factors)
	return columns, data
	
	#return columns, data


#def get_columns() -> list[dict]:
def get_columns(filters):
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	columns = [
		{"label": _("Date"), "fieldname": "date", "fieldtype": "Datetime", "width": 100},			
		
	]

	columns.extend(
		[
			{
				"label": _("In Qty"),
				"fieldname": "in_qty",
				"fieldtype": "Float",
				"width": 80,
				"convertible": "qty",
			},
			{
				"label": _("Out Qty"),
				"fieldname": "out_qty",
				"fieldtype": "Float",
				"width": 80,
				"convertible": "qty",
			},
			{
				"label": _("Bal Qty"),
				"fieldname": "qty_after_transaction",
				"fieldtype": "Float",
				"width": 120,
				"convertible": "qty",
			},			
			{
				"label": _("Voucher #"),
				"fieldname": "voucher_no",
				"fieldtype": "Dynamic Link",
				"options": "voucher_type",
				"width": 150,
			},			
			{
				"label": _("Party"),
				"fieldname": "customer",
				"width": 150,
			},
			#{"label": _("Narration"), "fieldname": "party_narr", "width": 70},
			{"label": _("Item Name"), "fieldname": "item_name", "width": 150},
			{
				"label": _("Main UOM"),
				"fieldname": "stock_uom",
				"width": 100,
			},
			{
				"label": _("Warehouse"),
				"fieldname": "warehouse",
				"width": 100,
			},
			#{"label": _("Item"),	"fieldname": "item_code","fieldtype": "Link","options": "Item",	"width": 150,},
		]
	)

	return columns


def get_data() -> list[list]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a list of cell values.
	"""
	return [
		["Row 1", 1],
		["Row 2", 2],
	]

def get_stock_ledger_entries(filters, items):
	from_date = get_datetime(filters.from_date + " 00:00:00")
	to_date = get_datetime(filters.to_date + " 23:59:59")

	sle = frappe.qb.DocType("Stock Ledger Entry")
	sdt = frappe.qb.DocType("Sales Invoice")
	query = (
		frappe.qb.from_(sle)
		.left_join(sdt)
		.on(sle.voucher_no == sdt.name)
		.select(
			sle.item_code,
			sle.posting_datetime.as_("date"),
			sle.warehouse,
			sle.posting_date,
			sle.posting_time,
			sle.actual_qty,
			sle.incoming_rate,
			sle.valuation_rate,
			sle.company,
			sle.voucher_type,
			sle.qty_after_transaction,
			sle.stock_value_difference,
			sle.serial_and_batch_bundle,
			sle.voucher_no,
			sle.stock_value,
			sle.batch_no,
			sle.serial_no,
			sle.project,
			sdt.customer,
		)
		.where((sle.docstatus < 2) & (sle.is_cancelled == 0) & (sle.posting_datetime[from_date:to_date]))
		.orderby(sle.posting_datetime)
		.orderby(sle.creation)
	)

	if items:
		query = query.where(sle.item_code.isin(items))
	
	""" for field in ["voucher_no", "project", "company"]:
		if filters.get(field) and field not in inventory_dimension_fields:
			query = query.where(sle[field] == filters.get(field)) """

	query = apply_warehouse_filter(query, sle, filters)

	return query.run(as_dict=True)

def get_items(filters):
	item = frappe.qb.DocType("Item")
	query = frappe.qb.from_(item).select(item.name)
	conditions = []

	if item_code := filters.get("item_code"):
		conditions.append(item.name == item_code)
	else:
		if brand := filters.get("brand"):
			conditions.append(item.brand == brand)
		if item_group := filters.get("item_group"):
			if condition := get_item_group_condition(item_group, item):
				conditions.append(condition)

	items = []
	if conditions:
		for condition in conditions:
			query = query.where(condition)
		items = [r[0] for r in query.run()]

	return items


def get_item_details(items, sl_entries, include_uom):
	item_details = {}
	if not items:
		items = list(set(d.item_code for d in sl_entries))

	if not items:
		return item_details

	item = frappe.qb.DocType("Item")
	query = (
		frappe.qb.from_(item)
		.select(item.name, item.item_name, item.description, item.item_group, item.brand, item.stock_uom)
		.where(item.name.isin(items))
	)

	if include_uom:
		ucd = frappe.qb.DocType("UOM Conversion Detail")
		query = (
			query.left_join(ucd)
			.on((ucd.parent == item.name) & (ucd.uom == include_uom))
			.select(ucd.conversion_factor)
		)

	res = query.run(as_dict=True)

	for item in res:
		item_details.setdefault(item.name, item)

	return item_details


def get_sle_conditions(filters):
	conditions = []
	if filters.get("warehouse"):
		warehouse_condition = get_warehouse_condition(filters.get("warehouse"))
		if warehouse_condition:
			conditions.append(warehouse_condition)

	return "and {}".format(" and ".join(conditions)) if conditions else ""


def get_opening_balance(filters, columns, sl_entries):
	if not (filters.item_code and filters.warehouse and filters.from_date):
		return

	from erpnext.stock.stock_ledger import get_previous_sle

	last_entry = get_previous_sle(
		{
			"item_code": filters.item_code,
			"warehouse_condition": get_warehouse_condition(filters.warehouse),
			"posting_date": filters.from_date,
			"posting_time": "00:00:00",
		}
	)

	# check if any SLEs are actually Opening Stock Reconciliation
	for sle in list(sl_entries):
		if (
			sle.get("voucher_type") == "Stock Reconciliation"
			and sle.posting_date == filters.from_date
			and frappe.db.get_value("Stock Reconciliation", sle.voucher_no, "purpose") == "Opening Stock"
		):
			last_entry = sle
			sl_entries.remove(sle)

	row = {
		"item_code": _("'Opening'"),
		"qty_after_transaction": last_entry.get("qty_after_transaction", 0),
		"valuation_rate": last_entry.get("valuation_rate", 0),
		"stock_value": last_entry.get("stock_value", 0),
	}

	return row


def get_warehouse_condition(warehouse):
	warehouse_details = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"], as_dict=1)
	if warehouse_details:
		return f" exists (select name from `tabWarehouse` wh \
			where wh.lft >= {warehouse_details.lft} and wh.rgt <= {warehouse_details.rgt} and warehouse = wh.name)"

	return ""
