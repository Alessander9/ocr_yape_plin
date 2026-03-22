import { initializeApp } from "https://www.gstatic.com/firebasejs/10.10.0/firebase-app.js";
import { getFirestore, collection, addDoc, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.10.0/firebase-firestore.js";

// Tu configuración de Firebase
const firebaseConfig = {
    apiKey: "AIzaSyD9oViGY4wtxBDoqDcnGMkwjhCM_c9Z1Ow",
    authDomain: "yapeplintransformador.firebaseapp.com",
    projectId: "yapeplintransformador",
    storageBucket: "yapeplintransformador.firebasestorage.app",
    messagingSenderId: "240902466092",
    appId: "1:240902466092:web:791176d915dcdaca2bbf89",
    measurementId: "G-VS5RW0TNNN"
};

// Inicializar Firebase
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

// Función global para guardar en Firestore
window.guardarReciboEnFirebase = async function(resultadoOCR) {
    try {
        const docRef = await addDoc(collection(db, "comprobantes"), {
            ...resultadoOCR,
            fechaRegistro: serverTimestamp()
        });
        console.log("Documento guardado en Firebase con ID: ", docRef.id);
        return true;
    } catch (e) {
        console.error("Error añadiendo documento a Firebase: ", e);
        return false;
    }
};