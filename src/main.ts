import "./styles.css";
import { App } from "./app.js";

const root = document.getElementById("app");
if (root === null) throw new Error("缺少 #app 掛載點");
void new App(root).start();
