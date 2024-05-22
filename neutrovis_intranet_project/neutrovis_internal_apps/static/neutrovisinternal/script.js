$(document).ready(function() {
    $('[data-bs-toggle="tooltip"]').each(function() {
        $(this).tooltip();
    });
    $('#claim_record').DataTable();
    $('#claim_verified').DataTable();
    $('#approved_claim_record').DataTable();
    $('#mytravelrequest').DataTable();
    $('#approvetravelrequest').DataTable();
    $('#approveoltravelrequest').DataTable();
    $('#display_profiles').DataTable();
    $('.dataTables_length').addClass('bs-select');
    $('#browser-message').hide();
    let userAgentString = navigator.userAgent;
    var isChrome = userAgentString.indexOf("Chrome") > -1;
    if (!isChrome) {
        $('#browser-message').show();
    }

    function fade_out() {
        $(".spaceformessage").fadeOut(1000, function() {
            $(this).remove();
        });
    }
    setTimeout(fade_out, 3500);

    var now = new Date(),
    maxDate = now.toISOString().substring(0,10);
    $('#invoice-date').prop('max', maxDate);
    $('#custom_exchange_rate').hide();
    function toggleAdvClaimSelection() {
        if ($('#has_adv_payment').is(':checked')) {
            $('#adv_claim_selection').show();
        } else {
            $('#adv_claim_selection').hide();
        }
    }
    toggleAdvClaimSelection();
    $('#has_adv_payment').change(toggleAdvClaimSelection);

    $('#id_use_own_rate').change(function() {
        if ($(this).is(':checked')) {
            $('#custom_exchange_rate').show();
        } else {
            $('#custom_exchange_rate').hide();
        }
    });
    $('#select_all').change(function() {
        var isChecked = $(this).is(':checked');
        $('table input[type="checkbox"]').prop('checked', isChecked);
    });
    $('.reject-claim-form').submit(function(e) {
        e.preventDefault();

        var rejectReason = prompt("Please enter the reason for rejection:");

        if (rejectReason !== null && rejectReason !== "") {
            $(this).append($('<input>').attr({
                type: 'hidden',
                name: 'reject_reason',
                value: rejectReason
            }));
            this.submit();
        } else {
            alert("Rejection reason is required.");
        }
    });
    $('.custom-select').change(function(){
        var container = $(this).closest('tr');
        var claimLineId = container.find('.claim_line_id').val();
        container.find('#save-btn-' + claimLineId).show();
    });
    $('.save-btn').click(function(){
        var rowData = [];
        var container = $(this).closest('tr');
        var claim_line_id = container.find(".claim_line_id").val();
        var expense_typeValue = container.find("#expense-type-select option:selected").val();
        var analytic_codeValue = container.find("#analytic-code-select option:selected").val();
        rowData.push({[claim_line_id] : {
            'expense_type': expense_typeValue,
            'analytic_code': analytic_codeValue,
        }});
        var csrftoken = $(this).data('csrf-token');
        $.ajax({
            url: '/finance_edit',
            type: 'POST',
            data: JSON.stringify(rowData),
            headers: {
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/json'
            },
            success: function(response) {
                $('.save-btn').hide();
                },
        });
    });
    $('custom-select').on('focus', function() {
        $(this).css('width', 'auto');
    }).on('blur change', function() {
        $(this).css('width', '200px');
    });
    $('.spinner-border').hide();
    $('#start-date').on('change', function() {
        var startDate = $(this).val();
        $('#end-date').attr('min', startDate);
        $('#end-date').val(startDate);
    });
});

