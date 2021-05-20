frappe.ui.form.on('App', {
	refresh: frm => {
		frm.remove_custom_button(__("Commit"));
        frm.remove_custom_button(__("Stash"));
        frm.remove_custom_button(__("Apply Stash"));
        frm.remove_custom_button(__("Pull & Rebase"));
		frm.remove_custom_button(__("Track Remote"));
        frm.remove_custom_button(__("Switch Branch"));
        frm.remove_custom_button(__("New Branch"));
        frm.remove_custom_button(__("Delete Branch"));
        frm.remove_custom_button(__("Fetch"));
	},
});
