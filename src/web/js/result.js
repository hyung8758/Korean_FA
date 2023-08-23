
const getData = () => {
    const url = "/result"
    const table = $('#resultTable').DataTable();
    const sendData = {"command":"result"};

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
          },
        body: JSON.stringify(sendData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success === true) {
            const history = data.history;
            table.clear();
            for(let i=0; i<history.length; i++) {
                table.row.add(history[i]);
            }
            table.draw();
        } else {
            alert("ERROR getdata: ", data.error);
        }
    })
    .catch(error => {
        alert("ERROR getdata: ", error);
    });
}


$(document).ready(function () {
    var isChrome = !!window.chrome;
    if(!isChrome)
    {
	document.write('<p>Chrome에서 실행하십시오.</p>');
	return;
    }
    const ws = new WebSocket(`ws://${window.location.host}/progress`);

    var table = $('#resultTable').DataTable({
        columnDefs: [
            {
                searchable: false,
                orderable: false,
                targets: 0,
                width: '20px',
                defaultContent: 1,
            },
            {
                targets: 1,
		        data: "date",
            },
            {
                targets: 2,
		        data: "language",
                width: '100px',
            },
            {
                targets: 3,
		        data: "totalAudio",
                width: '100px',
            },
            {
                targets: 4,
		        data: "progress",
                width: '50px',
            },
            {
                targets: 5,
                width: "30px",
                render: function ( data, type, row ) {
                    // values are stored in row.
                    const isButtonEnabled = row.progress === "100%";
                    const imageOpacity = isButtonEnabled ? 1 : 0.5;

                    const DownloadButton = document.createElement("button");
                    DownloadButton.type = "button";
                    DownloadButton.className = "download";
                    DownloadButton.innerHTML = `<svg width="16" height="16" fill="grey" class="bi bi-file-earmark-arrow-down-fill" viewBox="0 0 16 16" style="opacity: ${imageOpacity};">
                        <path d="M9.293 0H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V4.707A1 1 0 0 0 13.707 4L10 .293A1 1 0 0 0 9.293 0zM9.5 3.5v-2l3 3h-2a1 1 0 0 1-1-1zm-1 4v3.793l1.146-1.147a.5.5 0 0 1 .708.708l-2 2a.5.5 0 0 1-.708 0l-2-2a.5.5 0 0 1 .708-.708L7.5 11.293V7.5a.5.5 0 0 1 1 0z"/>
                        </svg>`;

                    if (!isButtonEnabled) {
                        DownloadButton.disabled = true;
                    } else {
                        DownloadButton.setAttribute('onclick', `downloadResult(${JSON.stringify(row)})`)
                    }
                    return DownloadButton.outerHTML;
                }
            },
            {
                targets: 6,
                width: "30px",
                render: function ( data, type, row ) {

                    const DeleteButton = document.createElement("button");
                    DeleteButton.type = "button";
                    DeleteButton.className = "delete";
                    DeleteButton.innerHTML = `<svg width="16" height="16" fill="grey" class="bi bi-trash3-fill" viewBox="0 0 16 16">
                        <path d="M11 1.5v1h3.5a.5.5 0 0 1 0 1h-.538l-.853 10.66A2 2 0 0 1 11.115 16h-6.23a2 2 0 0 1-1.994-1.84L2.038 3.5H1.5a.5.5 0 0 1 0-1H5v-1A1.5 1.5 0 0 1 6.5 0h3A1.5 1.5 0 0 1 11 1.5Zm-5 0v1h4v-1a.5.5 0 0 0-.5-.5h-3a.5.5 0 0 0-.5.5ZM4.5 5.029l.5 8.5a.5.5 0 1 0 .998-.06l-.5-8.5a.5.5 0 1 0-.998.06Zm6.53-.528a.5.5 0 0 0-.528.47l-.5 8.5a.5.5 0 0 0 .998.058l.5-8.5a.5.5 0 0 0-.47-.528ZM8 4.5a.5.5 0 0 0-.5.5v8.5a.5.5 0 0 0 1 0V5a.5.5 0 0 0-.5-.5Z"/>
                        </svg>`;
                    
                    DeleteButton.setAttribute('onclick', `stopProcess(${JSON.stringify(row)})`)
                    return DeleteButton.outerHTML;
                    },
	        },
        ],
	order: [[1, 'asc']],
    });
    table.on('order.dt search.dt', function () {
        table.column(0, { search: 'applied', order: 'applied' }).nodes().each(function (cell, i) {
            cell.innerHTML = i + 1;
        });
    }).draw();
    getData();
    // websocket listener.
    // it will update table progress information.
    ws.addEventListener('message', event => {
        const progressData = JSON.parse(event.data);
        const table = $('#resultTable').DataTable();
        table.rows().every(function () {
            const rowData = this.data(); // Get the data of the current row
            if (rowData.date === progressData.date) {
                rowData.progress = progressData.progress;
                this.data(rowData);
            };
        });
    });
});

const downloadResult = (rowValue) => {
    const url = "result"
    if(!rowValue) return;
    const date = rowValue['date'];
    const language = rowValue['language'];
    
    const result = confirm(`${date}을 다운로드합니다.`);
    if(!result) return;

    const sendData = {"command":"download", 
                        "date": date,
                        "language": language};
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
            },
        body: JSON.stringify(sendData)
    })
    .then(response => response.blob())
    .then(blob => {
        const downloadLink = document.createElement('a');
        const url = window.URL.createObjectURL(blob);
        downloadLink.href = url;
        downloadLink.download = `${date}-${language}.zip`;
        downloadLink.click();
        window.URL.revokeObjectURL(url);
    })
    .catch(error => {
        alert("ERROR downloader: ", error);
    });
}

const stopProcess = (rowValue) => {
    const url = "result"
    
    if(!rowValue) return;
    const date = rowValue['date'];
    const language = rowValue['language'];
    
    const result = confirm(`${date}을 삭제합니다.`);
    if(!result) return;
    
    const sendData = {"command":"remove", 
                        "date": date,
                        "language": language};
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
          },
        body: JSON.stringify(sendData)
    })
    .then(response => response.json())
    .then(data => {
        console.log("data: ", data)
        if (data.success === true) {
            const table = $('#resultTable').DataTable();
            const history = data.history;
            table.clear();
            for(let i=0; i<history.length; i++)
                table.row.add(history[i]);
            table.draw();
        } else {
            alert("ERROR stopprocess: ", data.error);
        }
    })
    .catch(error => {
        alert("ERROR stopprocess: ", error);
    });
}
