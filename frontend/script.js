const API_URL = "http://127.0.0.1:8000";


//UPLOAD PDF 

async function uploadPDF() {

    const fileInput = document.getElementById("pdfFile");

    const file = fileInput.files[0];

    const formData = new FormData();

    formData.append("file", file);

    document.getElementById("uploadResult").innerHTML = `
      <div class="loader"></div>
      <p>Uploading and processing PDF...</p>
   `;

    const response = await fetch(
        `${API_URL}/upload`,
        {
            method: "POST",
            body: formData
        }
    );

    const data = await response.json();

    document.getElementById("uploadResult").innerHTML =
        `<pre>${JSON.stringify(data, null, 2)}</pre>`;
}



//  ASK QUESTION 
async function askQuestion() {

    const question = document.getElementById("questionInput").value;
    
    document.getElementById("answerResult").innerHTML = `
     <div class="loader"></div>
     <p>Generating answer...</p>
   `; 

    const response = await fetch(
     `${API_URL}/ask`,
     {
        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({
            question: question
        })
     }
    );

    const data = await response.json();

    let html = `
        <h3>Answer</h3>
        <p>${data.answer}</p>
    `;


// SOURCES

    if (data.sources) {

      html += `
        <button onclick="toggleSources()">
            Show Sources
        </button>

        <div id="sourcesContainer" style="display:none; margin-top:20px;">
      `;

       data.sources.forEach(source => {

        html += `
            <div class="source-card">
            
                <strong>Page:</strong> ${source.page}

                <p>${source.content}</p>

            </div>
        `;
        });

      html += `</div>`;
    }

document.getElementById("answerResult").innerHTML = html;
}

function toggleSources() {

    const container = document.getElementById("sourcesContainer");

    if (container.style.display === "none") {

        container.style.display = "block";

    } else {

        container.style.display = "none";
    }
}

async function comparePapers() {

    const paper1 = document.getElementById("paper1").files[0];

    const paper2 = document.getElementById("paper2").files[0];

    const formData = new FormData();

    formData.append("file1", paper1);

    formData.append("file2", paper2);
    

    document.getElementById("compareResult").innerHTML = `
      <div class="loader"></div>
      <p>Comparing papers...</p>
    `;

    const response = await fetch(
        `${API_URL}/compare`,
        {
            method: "POST",
            body: formData
        }
    );

    const data = await response.json();

    const comparison = data.comparison;

    let html = `
        <h3>Comparison Result</h3>
    `;

    for (const section in comparison) {

        html += `
            <div class="source-card">

                <h3>${section}</h3>

                <strong>Paper 1:</strong>
                <p>${comparison[section].paper1}</p>

                <strong>Paper 2:</strong>
                <p>${comparison[section].paper2}</p>

            </div>
        `;
    }

    document.getElementById("compareResult").innerHTML = html;
}