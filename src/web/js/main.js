/*!
* Start Bootstrap - Simple Sidebar v6.0.6 (https://startbootstrap.com/template/simple-sidebar)
* Copyright 2013-2023 Start Bootstrap
* Licensed under MIT (https://github.com/StartBootstrap/startbootstrap-simple-sidebar/blob/master/LICENSE)
*/
// 
// Scripts
// 

// const newContentContainer = document.getElementById("contentContainer");
// const uploadMainBar = document.getElementById("uploadMainBar");
// const resultMainBar = document.getElementById("resultMainBar");

// const loadHtmlContent = htmlFile => {
//     const xhr = new XMLHttpRequest();
//     xhr.open("GET", htmlFile, true);
//     xhr.onreadystatechange = () => {
//         if (xhr.readyState === 4 && xhr.status === 200) {
//             newContentContainer.innerHTML = xhr.responseText;
//           }
//     }
//     xhr.send();
// }

// uploadMainBar.addEventListener("click", event => {
//     event.preventDefault();
//     loadHtmlContent("html/upload.html");
//     });
// resultMainBar.addEventListener("click", event => {
//     event.preventDefault();
//     loadHtmlContent("html/result.html");
//     });

window.addEventListener('DOMContentLoaded', event => {

    // Toggle the side navigation
    const sidebarToggle = document.body.querySelector('#sidebarToggle');
    if (sidebarToggle) {
        // Uncomment Below to persist sidebar toggle between refreshes
        // if (localStorage.getItem('sb|sidebar-toggle') === 'true') {
        //     document.body.classList.toggle('sb-sidenav-toggled');
        // }
        sidebarToggle.addEventListener('click', event => {
            event.preventDefault();
            document.body.classList.toggle('sb-sidenav-toggled');
            localStorage.setItem('sb|sidebar-toggle', document.body.classList.contains('sb-sidenav-toggled'));
        });
    }
});


