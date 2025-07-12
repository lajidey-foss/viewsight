frappe.ui.form.on("Sales Invoice", {
    //
    refresh(frm){
        //
        if (frm.is_new()){
            //cur_frm.set_value("update_stock", 1);
            frm.doc.update_stock = 1;
        }
    },
})