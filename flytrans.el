;;; flytrans.el --- Fly Translation File
;;
;; Copyright (c) 2018-2020 JiangtaoWu & Contributors
;;
;; Author: Jiangtao Wu <jiangtaowoo@gmail.com>
;; URL: https://github.com/jiangtaowoo/flytranslation
;;
;; This file implement the method for English translation
;; while reading text in Emacs.
;;
;;; License: GPLv3

;;*************************************BEGIN OF FLY-TRANSLATE*************************************
;;阅读过程中调用的翻译函数
;;需根据HOME路径自行修改
(defun fly-translate ()
    "translate while reading by calling python script"
    (interactive)
    ;;变量定义
    (defconst fly-trans-wait-seconds 5)
    (defconst fly-trans-program-name "flytrans.py")
    (defconst fly-trans-flashcard-name "flashcard.txt")
    (defconst fly-trans-home-path
      (cond ((eq system-type 'windows-nt)
              (setq script (format "c:/emacs25/flytrans/")))
            ((eq system-type 'gnu/linux)
              (setq script (format "/home/jtwu/flytrans/")))))
    ;;-------sub function: get-word-or-region----------
    ;;获取当前 buffer 的选区 region, 或者当前光标所在的单词
    (defun get-word-or-region ()
      "if mark exist, return beg, end;
        else return current word on cursor as region"
      (interactive)
      (let (beg end)
        (if (use-region-p)
            (setq beg (region-beginning) end (region-end))
            (save-excursion
              (skip-chars-backward "A-Za-z")
              (setq beg (point))
              (skip-chars-forward "A-Za-z")
              (setq end (point))))
        (buffer-substring-no-properties beg end)
        ))
    ;;-------sub function: get-sentence----------
    ;;获取当前 buffer 的选区 region, 或者当前光标所在的位置对应的句子
    (defun get-sentence ()
      "return sentence"
      (interactive)
      (defconst fly-trans-sbd-magic '("www" "Mr" "Mrs"))
      ;;-------sub function: check-sbd----------
      ;;判断当前buffer的当前位置是否属于sentence boundary
      ;;当以下条件满足, 返回t, 否则返回nil
      ;;fly-trans-sbd-magic对应的单词不在search-backword范围内
      (defun check-sbd ()
        "check current point is sentence boundary or not"
        (interactive)
        (let ((magic-len (length fly-trans-sbd-magic))
              (i 0)
              (m 0)
              (pos (point))
              (lenm 0)
              (teststr 0)
              (result t))
          (save-excursion
                  (while (and (< i magic-len) result)
                    (progn
                      (setq m (car (nthcdr i fly-trans-sbd-magic)))
                      (setq i (+ i 1))
                      (setq lenm (+ 2 (length m)))
                      (goto-char (- pos lenm))
                      (setq teststr (buffer-substring-no-properties (point) pos))
                      (setq result (not (string-match-p (regexp-quote m) teststr)))))
                  )
          (and result t)))
      ;;main body of get sentence
      (let (beg end pos trytimes)
        (if (use-region-p)
            (setq beg (region-beginning) end (region-end))
            (setq beg (point) end (point)))
        (progn
          (save-excursion
            (goto-char beg)
            (backward-sentence)
            (setq trytimes 0)
            (while (and (< trytimes 3) (not (check-sbd)))
              (progn
                (setq trytimes (+ 1 trytimes))
                (backward-sentence)))
            (setq beg (point))
            (goto-char end)
            (forward-sentence)
            (setq trytimes 0)
            (while (and (< trytimes 3) (not (check-sbd)))
              (progn
                (setq trytimes (+ 1 trytimes))
                (forward-sentence)))
            (setq end (point))
            ))
        (buffer-substring-no-properties beg end)))
    ;;-------sub function: trans-word-or-region----------
    ;;使用 start-process 调用 python 脚本, 翻译指定单词, 并输出到指定名字 buffer 中
    (defun trans-word-or-region (word sentence bufname)
      "translate the world through internet by calling python script"
      (interactive)
      (let (script)
        (setq script (concat fly-trans-home-path fly-trans-program-name))
        (start-process "trans-sprocess" bufname "python" script word sentence)
        ))
    ;;-------sub function: check-flashcard----------
    ;;检查是否已经有结果返回
    (defun check-flashcard (bufname)
      "return t if the translate result is in the buffer, else return nil"
      (interactive)
        (save-excursion
          (set-buffer (get-buffer-create bufname))
          (equal "Process trans-sprocess finished"
            (progn
              (goto-char (point-max))
              (if (> (count-lines (point-min) (point-max)) 0)
                (progn
                  (forward-line (- 1))
                  (buffer-substring-no-properties (point) (- (point-max) 1)))
                ())))))
    ;;-------sub function: prettify-flashcard----------
    ;;处理 buffer 内容, 删除无效内容
    (defun prettify-flashcard (bufname)
      "delete last 4 lines of buffer *FlashCard*"
      (interactive)
        (if (check-flashcard bufname)
          (save-excursion
            (set-buffer (get-buffer-create bufname))
            (progn
                (goto-char (point-max))
                (forward-line (- 2))
                (delete-region (point) (point-max))
                (save-buffer)))))
    ;;-------sub function: buffer-contains-substring----------
    ;;某个 buffer 是否包含指定字符串(行首单词), 如果包含, 定位至该位置, 返回 t
    (defun buffer-contains-substring (bufname strfind)
      "if the buffer contains strfind, if yes, goto-char and return t"
      (interactive)
      (save-excursion
        (set-buffer (get-buffer-create bufname))
        (let ((found nil) (pos 1) (pos1 1))
          (goto-char (point-min))
          (while (and (not found) (< (point) (point-max)))
            (progn
                (setq pos1 (point))
                (skip-chars-forward "A-Za-z")
                (if (equal strfind (buffer-substring-no-properties (+ pos1) (point)))
                    (progn
                      (setq found t)
                      (setq pos (- (point) (length strfind)))))
                (forward-line 1)))
          (if (not found)
            (setq pos nil)
            (progn
                (goto-char pos)
                (set-window-point (get-buffer-window (current-buffer)) pos)
                (other-window 1)
                (recenter-top-bottom 'top)
                (other-window (- 1))
                (+ pos))))))
    ;;-------sub function: display-flashcard----------
    ;;在右侧窗口显示 FlashCard 的内容
    (defun display-flashcard (bufname)
      "display flashcard in right window"
      (interactive)
      (save-excursion
        (set-buffer (get-buffer-create bufname))
          ;;在右侧窗口显示 FlashCard 内容
        (if (eq (length (window-list)) 1)
            (split-window-right))
        (display-buffer-use-some-window (get-buffer bufname)
            '(
              (side . right)
              (slot . 1)))
        (goto-char (point-max))
        (forward-line (- 1))))
    ;;-------sub function: open-file-flashcard----------
    ;;打开 flashcard 对应的文件, 在右侧窗口显示
    (defun open-file-flashcard (filename)
      "open flashcard file and display in side window"
      (interactive)
      (if (eq (length (window-list)) 1)
          (split-window-right))
      (save-excursion
        (let (fname)
          (setq fname filename)
          (if (not (get-buffer fname))
            (progn
              (other-window 1)
              (find-file (concat fly-trans-home-path fname))
              (other-window (- 1)))
            (display-flashcard fname)))))
    ;;-------fly-translate main body----------
    ;;翻译主体过程
    (let (word sentence bufname waits)
      (setq bufname fly-trans-flashcard-name)
      (setq word (get-word-or-region))
      (setq sentence (get-sentence))
      ;;如果生词库对应的文件未打开, 则打开它
      (if (not (get-buffer bufname))
        (open-file-flashcard bufname))
      ;;如果 buffer 有修改内容, 则保存它
      (save-excursion
        (set-buffer (get-buffer bufname))
        (if (buffer-modified-p)
            (save-buffer)))
      ;;如果单词不包含在已经找到的 FlashCard 中, 发起一次新的查询
      (if (not (buffer-contains-substring bufname word))
        (progn
          ;;如果有上次未清除的多余输出, 先进行清除
          (setq waits 0)
          (prettify-flashcard bufname)
          (trans-word-or-region word sentence bufname)
          (while (and (< waits fly-trans-wait-seconds) (not (check-flashcard bufname)))
                  (progn
                    (setq waits (+ waits 1))
                    (sit-for 1)))
          (if (< waits fly-trans-wait-seconds)
              (prettify-flashcard bufname))
          ;;在窗口显示 FlashCard 内容
          (display-flashcard bufname)
          (buffer-contains-substring bufname word)))))

;;绑定快捷键
(global-set-key (kbd "C-c t") 'fly-translate)
;;*************************************END OF FLY-TRANSLATE*************************************

