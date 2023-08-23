// console.clear();
('use strict');

const loadingSpinner = document.getElementById('loadingSpinner');
// Drag and drop - single or multiple image files
// https://www.smashingmagazine.com/2018/01/drag-drop-file-uploader-vanilla-js/
// https://codepen.io/joezimjs/pen/yPWQbd?editors=1000
(function () {
  'use strict';
  
  var isChrome = !!window.chrome;
      if(!isChrome) {
      document.write('<p>Chrome에서 실행하십시오.</p>');
      return;
      }
  // Four objects of interest: drop zones, input elements, gallery elements, and the files.
  // dataRefs = {files: [image files], input: element ref, gallery: element ref}

  const preventDefaults = event => {
    event.preventDefault();
    event.stopPropagation();
  };

  const highlight = event =>
    event.target.classList.add('highlight');
  
  const unhighlight = event =>
    event.target.classList.remove('highlight');

  const getInputAndGalleryRefs = element => {
    const zone = element.closest('.upload_dropZone') || false;
    const gallery = zone.querySelector('.upload_gallery') || false;
    const input = zone.querySelector('input[type="file"]') || false;
    return {input: input, gallery: gallery};
  }

  const handleDrop = event => {
    const dataRefs = getInputAndGalleryRefs(event.target);
    dataRefs.files = event.dataTransfer.files;
    handleFiles(dataRefs);
  }


  const eventHandlers = zone => {

    const dataRefs = getInputAndGalleryRefs(zone);
    if (!dataRefs.input) return;

    // Prevent default drag behaviors
    ;['dragenter', 'dragover', 'dragleave', 'drop'].forEach(event => {
      zone.addEventListener(event, preventDefaults, false);
      document.body.addEventListener(event, preventDefaults, false);
    });

    // Highlighting drop area when item is dragged over it
    ;['dragenter', 'dragover'].forEach(event => {
      zone.addEventListener(event, highlight, false);
    });
    ;['dragleave', 'drop'].forEach(event => {
      zone.addEventListener(event, unhighlight, false);
    });

    // Handle dropped files
    zone.addEventListener('drop', handleDrop, false);

    // Handle browse selected files
    dataRefs.input.addEventListener('change', event => {
      dataRefs.files = event.target.files;
      handleFiles(dataRefs);
    }, false);

  }


  // Initialise ALL dropzones
  const dropZones = document.querySelectorAll('.upload_dropZone');
  for (const zone of dropZones) {
    eventHandlers(zone);
  }

  // NOTE: we will accept auio file and text.
  // No 'image/gif' or PDF or webp allowed here, but it's up to your use case.
  // Double checks the input "accept" attribute
  const isRightFile = file => 
    ['audio/wav', 'text/plain'].includes(file.type);

  function previewFiles(dataRefs) {
    if (!dataRefs.gallery) return;
    window.dataRefs = dataRefs;
    const fileListUpContainer = document.getElementById('fileListUpContainer');
    // for (const file of dataRefs.files) {
    dataRefs.files.forEach((eachFile, idx) => {
      // add a list.
      const listItem = document.createElement('li');
      listItem.textContent = eachFile.name;
      // append class value.
      listItem.classList.add('list-group-item','list-group-item-success');
      // add a span.
      const spanItem = document.createElement('span');
      spanItem.id = `file${idx}`
      spanItem.textContent = 'ready';
      spanItem.classList.add('badge', 'alert-success', 'pull-right');
      listItem.appendChild(spanItem);
      fileListUpContainer.appendChild(listItem);
    })
      // let reader = new FileReader();
      // reader.readAsDataURL(file);
      // reader.onloadend = function() {
      //   let img = document.createElement('img');
      //   img.className = 'upload_file mt-2';
      //   img.setAttribute('alt', file.name);
      //   img.src = reader.result;
      //   dataRefs.gallery.appendChild(img);
      // }
    //}
  }


  // Handle both selected and dropped files
  const handleFiles = dataRefs => {

    let files = [...dataRefs.files];

    // Remove unaccepted file types
    files = files.filter(item => {
      if (!isRightFile(item)) {
        console.log('Not an auido nor text, ', item.type);
      }
      return isRightFile(item) ? item : null;
    });

    if (!files.length) return;
    dataRefs.files = files;

    previewFiles(dataRefs);
    // audioUpload(dataRefs);
  }

})();

// send a data
const submitButton = document.querySelector('#js-upload-submit');

submitButton.addEventListener('click', function(event) {
  event.preventDefault();
  loadingSpinner.style.display = 'flex';
  if (typeof dataRefs !== 'undefined') {
    const url = '/upload';
    // Multiple source routes, so double check validity
    if (!dataRefs.files || !dataRefs.input) return;
    const formData = new FormData();
    
    let shouldExit = false;
    // add formData and additional parameters.
    const selectedLanguage = document.getElementById('selectLanguage').value;
    console.log("selected lang: ",selectedLanguage)
    formData.append("lang", selectedLanguage)
    const fileListUpContainer = document.getElementById('fileListUpContainer');
    dataRefs.files.forEach((item, idx) => {
      const spanContainer = document.getElementById(`file${idx}`);
      // if this item file is already uploaded? ignore it.
      if (spanContainer.textContent === "uploaded") {
        shouldExit = true;
        // spanContainer.remove()
      } else {
        formData.append(item.name, item);
        spanContainer.textContent = "uploading";
      }
    })

    if (shouldExit) {
      alert("uploaded files are found. Please re-upload files.");
      location.reload(); // Exit the function
      return;
    }

    fetch(url, {
      method: 'POST',
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      console.log("data: ", data)
      if (data.success === true) {
        // if files are succesffuly uploaded. change status to uploaded.
        dataRefs.files.forEach((item, idx) => {
          const spanContainer = document.getElementById(`file${idx}`);
          spanContainer.textContent = "uploaded";
        })
      } else {
        alert("ERROR downloader: ", data.error);
      }
      loadingSpinner.style.display = 'none';
    })
    .catch(error => {
      console.error('errored: ', error);
    });
  } else {
    alert("Nothing to submit")
    loadingSpinner.style.display = 'none';
  }
})

// + function($) {
//     'use strict';

//     // UPLOAD CLASS DEFINITION
//     // ======================

//     var dropZone = document.getElementById('drop-zone');
//     var uploadForm = document.getElementById('js-upload-form');

//     var startUpload = function(files) {
//         console.log(files)
//     }

//     uploadForm.addEventListener('submit', function(e) {
//         var uploadFiles = document.getElementById('js-upload-files').files;
//         e.preventDefault()

//         startUpload(uploadFiles)
//     })

//     dropZone.ondrop = function(e) {
//         e.preventDefault();
//         this.className = 'upload-drop-zone';

//         startUpload(e.dataTransfer.files)
//     }

//     dropZone.ondragover = function() {
//         this.className = 'upload-drop-zone drop';
//         return false;
//     }

//     dropZone.ondragleave = function() {
//         this.className = 'upload-drop-zone';
//         return false;
//     }

// }(jQuery);