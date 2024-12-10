$(document).ready(function() {
    // Initialize Chosen
    $('.chosen-select').chosen({
        width: '100%',
        search_contains: true
    });

    // Initialize both DataTables
    const trialsTable = $('#trialsTable').DataTable({
        columns: [
            { 
                data: 'trial_id', 
                title: 'Trial ID',
            },
            { 
                data: 'title', 
                title: 'Title', 
            },
            { 
                data: 'lead_sponsor_name', 
                title: 'Sponsor Name' 
            },
            { 
                data: 'phase', 
                title: 'Phase' 
            },
            { 
                data: 'interventions',
                title: 'Drug Interventions',
                render: function(data) {
                    return Array.isArray(data) ? data.join(', ') : '';
                }
            }
        ],
        dom: 'Bfrtip', 
        pageLength: 10,
        buttons: ['csv', 'excel'],
        order: [[0, 'asc']],
        data: []
    });

    const drugTable = $('#drugTable').DataTable({
        columns: [
            { 
                data: 'drug', 
                title: 'Drug Name',
                width: '200px',
                className: 'text-left'
            },
            { 
                data: 'count', 
                title: 'Number of Trials',
                width: '80px',
                className: 'text-center'
            }
        ],
        dom: 'Bfrtip', 
        pageLength: 10,
        buttons: ['csv', 'excel'],
        order: [[1, 'desc']],
        data: []
    });

    // Handle view toggle
    $('#showTrials').click(function() {
        $(this).addClass('active');
        $('#showDrugs').removeClass('active');
        $('#trialsTableContainer').addClass('active');
        $('#drugTableContainer').removeClass('active');
        trialsTable.columns.adjust();
    });

    $('#showDrugs').click(function() {
        $(this).addClass('active');
        $('#showTrials').removeClass('active');
        $('#drugTableContainer').addClass('active');
        $('#trialsTableContainer').removeClass('active');
        drugTable.columns.adjust();
    });

    // Handle filter application
    $('#applyFilters').on('click', function() {
        const filters = {
            phases: $('#trialPhase').val(),
            status: $('#trialStatus').val(),
            study_type: $('#trialType').val(),
            industry_sponsor: $('#industrySponsor').val(),
            mesh_condition: $('#meshCondition').val()
        };
        console.log(filters)
        $.ajax({
            url: '/trials',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(filters),
            success: function(response) {
                // Update trials table
                trialsTable.clear().rows.add(response.data).draw();
                
                // Convert drug counts to array format for DataTable
                const drugData = Object.entries(response.drug_counts).map(([drug, count]) => ({
                    drug: drug,
                    count: count
                }));
                
                // Update drug counts table
                drugTable.clear().rows.add(drugData).draw();
            },
            error: function(xhr, status, error) {
                console.error('Error fetching data:', error);
                alert('Error fetching data. Please try again.');
            }
        });
    });
});