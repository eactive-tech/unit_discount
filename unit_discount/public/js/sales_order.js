frappe.ui.form.on('Sales Order', {
    before_save: function(frm) {
        frm.doc.items.forEach(row => {
            row.custom_set_rate_ = row.rate;
            row.custom_set_amount = row.amount;
        });
        frm.refresh_field("items");
    },
    after_save: function(frm) {
        frappe.call({
            method: "unit_discount.overrides.custom_price_list.rate_amount_update",
            args: {
                items: frm.doc.items
            },
            callback: function(r) {
                if (r.message) {
                    // frappe.msgprint(r.message);
                    frm.reload_doc(); 
                }
            }
           
        });
    }
});
