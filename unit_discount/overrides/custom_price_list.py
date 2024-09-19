import copy
import json
import re

import frappe
from frappe import _, throw
from frappe.model.document import Document
from frappe.utils import cint, flt

def apply_price_discount_rule(pricing_rule, item_details, args):
	item_details.pricing_rule_for = pricing_rule.rate_or_discount

	if (pricing_rule.margin_type in ["Amount", "Percentage", "Per Unit"] and pricing_rule.currency == args.currency) or (
		pricing_rule.margin_type == "Percentage"
	):
		
		item_details.margin_type = pricing_rule.margin_type
		item_details.has_margin = True

		if pricing_rule.margin_type == "Per Unit":
			conversion = get_item_conversion(args.get('item_code'), pricing_rule.custom_margin_unit)
			item_details.margin_rate_or_amount = pricing_rule.custom_margin_rate_per_unit * conversion

		else:

			if pricing_rule.apply_multiple_pricing_rules and item_details.margin_rate_or_amount is not None:
				item_details.margin_rate_or_amount += pricing_rule.margin_rate_or_amount
			else:
				item_details.margin_rate_or_amount = pricing_rule.margin_rate_or_amount

	if pricing_rule.rate_or_discount == "Rate":
		pricing_rule_rate = 0.0
		if pricing_rule.currency == args.currency:
			pricing_rule_rate = pricing_rule.rate

		# TODO https://github.com/frappe/erpnext/pull/23636 solve this in some other way.
		if pricing_rule_rate:
			is_blank_uom = pricing_rule.get("uom") != args.get("uom")
			# Override already set price list rate (from item price)
			# if pricing_rule_rate > 0
			item_details.update(
				{
					"price_list_rate": pricing_rule_rate
					* (args.get("conversion_factor", 1) if is_blank_uom else 1),
				}
			)
		item_details.update({"discount_percentage": 0.0})

	for apply_on in ["Discount Amount", "Discount Percentage", "Discount Per Unit"]:

		if pricing_rule.rate_or_discount != apply_on:
			continue

		if apply_on == 'Discount Per Unit':
			field = 'custom_discount_per_unit_rate'
			value = pricing_rule.get(field, 0)

			conversion = get_item_conversion(args.get('item_code'), pricing_rule.custom_discount_unit)

			item_details['custom_discount_per_unit'] = pricing_rule[field]
			item_details['custom_discount_per_unit_amount'] = conversion * args.qty * pricing_rule[field]
			item_details['discount_amount'] = pricing_rule[field] * conversion
		
		field = frappe.scrub(apply_on)
		if pricing_rule.apply_discount_on_rate and item_details.get("discount_percentage"):
			# Apply discount on discounted rate
			item_details[field] += (100 - item_details[field]) * (pricing_rule.get(field, 0) / 100)
		elif args.price_list_rate:
			value = pricing_rule.get(field, 0)
			calculate_discount_percentage = False
			if field == "discount_percentage":
				field = "discount_amount"
				value = args.price_list_rate * (value / 100)
				calculate_discount_percentage = True

			if field not in item_details:
				item_details.setdefault(field, 0)

			item_details[field] += value if pricing_rule else args.get(field, 0)
			if calculate_discount_percentage and args.price_list_rate and item_details.discount_amount:
				item_details.discount_percentage = flt(
					(flt(item_details.discount_amount) / flt(args.price_list_rate)) * 100
				)
		else:
			if field not in item_details:
				item_details.setdefault(field, 0)

			item_details[field] += pricing_rule.get(field, 0) if pricing_rule else args.get(field, 0)


def get_item_conversion(item_code, uom):
	item = frappe.get_doc("Item", item_code)

	for u in item.uoms:
		if u.uom == uom:
			return u.conversion_factor
	
	return 1