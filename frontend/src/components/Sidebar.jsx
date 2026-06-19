import { Link } from "react-router-dom";
import {
  FaHome,
  FaImage,
  FaVideo,
  FaExclamationTriangle,
  FaInfoCircle,
} from "react-icons/fa";

function Sidebar() {
  return (
    <div className="w-64 bg-slate-900 text-white h-screen p-5">
      <h2 className="text-3xl font-bold mb-10">
        SafeVision AI
      </h2>

      <ul className="space-y-5">
        <li>
          <Link
            to="/"
            className="flex items-center gap-3 hover:text-blue-400"
          >
            <FaHome />
            Dashboard
          </Link>
        </li>

        <li>
          <Link
            to="/image-detection"
            className="flex items-center gap-3 hover:text-blue-400"
          >
            <FaImage />
            Image Detection
          </Link>
        </li>

        <li>
          <Link
            to="/video-detection"
            className="flex items-center gap-3 hover:text-blue-400"
          >
            <FaVideo />
            Video Detection
          </Link>
        </li>

        <li>
          <Link
            to="/violations"
            className="flex items-center gap-3 hover:text-blue-400"
          >
            <FaExclamationTriangle />
            Violations
          </Link>
        </li>

        <li>
          <Link
            to="/about"
            className="flex items-center gap-3 hover:text-blue-400"
          >
            <FaInfoCircle />
            About
          </Link>
        </li>
      </ul>
    </div>
  );
}

export default Sidebar;