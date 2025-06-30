
// frappe.provide("frappe.views");

frappe.views.QueryReport = class QueryReport extends frappe.views.QueryReport {
	show_footer_message() {
		this.$report_footer && this.$report_footer.remove();
		this.$report_footer = $(`<div class="report-footer text-muted"></div>`).appendTo(this.page.main);
		if (this.tree_report) {
			this.$tree_footer = $(`<div class="tree-footer col-md-6">
				<button class="btn btn-xs btn-default" data-action="expand_all_rows">
					${__('Expand All')}</button>
				<button class="btn btn-xs btn-default" data-action="collapse_all_rows">
					${__('Collapse All')}</button>
			</div>`);
			$(this.$report_footer).append(this.$tree_footer);
			this.$tree_footer.find('[data-action=collapse_all_rows]').show();
			this.$tree_footer.find('[data-action=expand_all_rows]').hide();
		}

		// const message = __('For comparison, use >5, <10 or =324. For ranges, use 5:10 (for values between 5 & 10).');
		// const execution_time_msg = __('Execution Time: {0} sec', [this.execution_time || 0.1]);

		// this.$report_footer.append(`<div class="col-md-12">
		// 	<span">${message}</span><span class="pull-right">${execution_time_msg}</span>
		// </div>`);
	}
}