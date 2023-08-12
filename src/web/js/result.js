
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
	console.log("now ready.")
	$('#resultTable').DataTable();
    // var table = $('#resultTable').DataTable({
    //     columnDefs: [
	//     {
	// 	"targets": 5,
	// 	"width": "20px",
	// 	"createdCell": function (td, cellData, rowData, row, col) {
	// 	    var btn = $(BTN_STOP)[0];
	// 	    btn.id = `bt-stop-${row}`
	// 	    btn.className = "delete"
	// 	    btn.addEventListener("click", stopProcess);
	// 	    td.appendChild(btn);
	// 	},
	//     },
    //     ],
    // });
 
    // getData();
    // setInterval(getData, 2000);
});
function stopProcess(e) {
    var table = $("#tableLogs").DataTable();
    let rowitem = $($(e).parent()[0]).parent()[0];
    if(!rowitem)
	return;
    var row = table.row(rowitem);
    let name = row.data()['name'];
    let address = row.data()['address'];

    let result = confirm(`${name}을 삭제합니다.`);
    let command = "remove";
    if(!result) return;

    let senddata = copyFormat(COMM_DATA_FORMAT);
    senddata['page'] = 3;
    let cont = copyFormat(COMM_CONTENT_FORMAT);
    cont['name'] = name;
    cont['address'] = address;
    cont['command'] = command;
    senddata['content'].push(cont);

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
		table.row.add(content[i]);
	    }
	    table.draw();
	}
    };
    xhr.onerror = function() {
	alert("데이터 송신 실패.");
    };
    xhr.send(JSON.stringify(senddata));
}
