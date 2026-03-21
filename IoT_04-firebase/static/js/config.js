  // Import the functions you need from the SDKs you need
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
import { getDatabase } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-database.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-analytics.js";
  // TODO: Add SDKs for Firebase products that you want to use
  // https://firebase.google.com/docs/web/setup#available-libraries

  // Your web app's Firebase configuration
  // For Firebase JS SDK v7.20.0 and later, measurementId is optional
const firebaseConfig = {
    apiKey: "AIzaSyC9Msq1y7OPm4RVaTZ3I_hYA_5QT1i45T8",
    authDomain: "iot-nhom4-3e99a.firebaseapp.com",
    databaseURL: "https://iot-nhom4-3e99a-default-rtdb.asia-southeast1.firebasedatabase.app", // QUAN TRỌNG
    projectId: "iot-nhom4-3e99a",
    storageBucket: "iot-nhom4-3e99a.firebasestorage.app",
    messagingSenderId: "399931249650",
    appId: "1:399931249650:web:51c4a7b5387678cb23d16b",
    measurementId: "G-7D4W6XDB3Q"
    };

  // Initialize Firebase
const app = initializeApp(firebaseConfig);
const db = getDatabase(app);
const auth = getAuth(app);
const analytics = getAnalytics(app);

export { db, auth }; // Xuất 'db' và 'auth' ra ngoài để có thể sử dụng trong các file khác