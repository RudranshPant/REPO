function changeText(){
    let fpara = document.getElementById('fpara');
    fpara.textContent = "Hello Babbar"
    
}
let fpara = document.getElementById('fpara');

fpara.addEventListener('click', changeText);