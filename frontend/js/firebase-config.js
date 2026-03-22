import { initializeApp } from "https://www.gstatic.com/firebasejs/10.10.0/firebase-app.js";
import { getFirestore, collection, addDoc, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.10.0/firebase-firestore.js";

// TODO: Reemplaza esto con la configuración de tu proyecto en Firebase
const firebaseConfig = {
  apiKey: "TU_API_KEY",
  authDomain: "tu-proyecto.firebaseapp.com",
  projectId: "tu-proyecto",
  storageBucket: "tu-proyecto.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abcdef"
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
