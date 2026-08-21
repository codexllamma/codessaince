import { Routes, Route, Navigate } from 'react-router-dom'
import { ToastContainer } from 'react-toastify'
import 'react-toastify/dist/ReactToastify.css'

import Loading from './Pages/Loading'
import Landing from './Pages/Landing'
import RoleSelect from './Pages/RoleSelect'

import Login from './Pages/User/LoginSelect'
import CircularSelect from './Pages/User/CircularSelect'
import LanguageSelect from './Pages/User/LanguageSelect'
import AvatarSelect from './Pages/User/AvatarSelect'
import Videos from './Pages/User/Videos'

import UploadPdf from './Pages/Admin/UploadPdf'
import SplitScreenCategorize from './Pages/Admin/SplitScreenCategorize'
import NoticeIngest from './Pages/Admin/NoticeIngest'
import FactGrounding from './Pages/Admin/FactGrounding'
import StoryBoard from './Pages/Admin/StoryBoard'
import VoiceKaraoke from './Pages/Admin/VoiceKaraoke'
import OfficerApproval from './Pages/Admin/OfficerApproval'

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Loading />} />
        <Route path="/landing" element={<Landing />} />
        <Route path="/role" element={<RoleSelect />} />

        <Route path="/user/login" element={<Login />} />
        <Route path="/user/circulars" element={<CircularSelect />} />
        <Route path="/user/language" element={<LanguageSelect />} />
        <Route path="/user/avatar" element={<AvatarSelect />} />
        <Route path="/user/videos" element={<Videos />} />

        <Route path="/admin/upload" element={<UploadPdf />} />
        <Route path="/admin/categorize" element={<SplitScreenCategorize />} />
        <Route path="/admin/ingest" element={<NoticeIngest />} />
        <Route path="/admin/fact-grounding" element={<FactGrounding />} />
        <Route path="/admin/storyboard" element={<StoryBoard />} />
        <Route path="/admin/voice-karaoke" element={<VoiceKaraoke />} />
        <Route path="/admin/approval" element={<OfficerApproval />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ToastContainer
        position="top-center"
        autoClose={2000}
        hideProgressBar
        newestOnTop
        closeOnClick
        pauseOnHover
        theme="light"
        toastClassName="!font-body !rounded-2xl !bg-white/95 !text-plum-900 !shadow-glow !mt-2"
        limit={3}
      />
    </>
  )
}
