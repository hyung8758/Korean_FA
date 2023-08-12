const getData = () => {
    var table = $('#resultTable').DataTable();
    let senddata = {'sender':'client',
		    'page': 3,
		    'content': []};
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/server');
    xhr.responseType='json';
    xhr.onload = () => {
	if(xhr.status == 200)
	{
            var data = xhr.response;
	    const content = data.content;
	    table.clear();
	    for(let i=0; i<content.length; i++)
	    {
		let rowdata = [content[i]['name'], content[i]['address']]
		table.row.add(rowdata);
	    }
	    table.draw();
	}
    };
    xhr.onerror = function() {
	clearInterval(timerId);
	alert("데이터 송신 실패.");
    };
    xhr.send(JSON.stringify(senddata));
}


$(document).ready(function () {

    // var table = $('#resultTable').DataTable({
    //     columnDefs: [
    //     ],
    // });
    var table = $('#resultTable').DataTable({
        columnDefs: [
	    {
		"targets": 5,
		"width": "20px",
		"createdCell": function (td, cellData, rowData, row, col) {
		    var btn = $(BTN_STOP)[0];
		    btn.id = `bt-stop-${row}`
		    btn.className = "delete"
		    btn.addEventListener("click", stopProcess);
		    td.appendChild(btn);
		},
	    },
        ],
    });
 
    getData();
    // setInterval(getData, 2000);
});
